// Vision Companion — main orchestration.
// Wires AudioPipeline + VideoPipeline + SessionSocket together.

import { setState } from "./a11y.js";
import { AudioPipeline } from "./audio.js";
import { VideoPipeline } from "./video.js";
import { SessionSocket } from "./ws.js";

const $ = (id) => document.getElementById(id);

// -- Backend URL resolution --------------------------------------------------
// Priority: ?backend=wss://... > window.__BACKEND__ > same-origin /ws/session
function resolveBackendUrl() {
  const params = new URLSearchParams(location.search);
  const explicit = params.get("backend");
  if (explicit) return explicit;
  if (window.__BACKEND__) {
    const base = window.__BACKEND__.replace(/^http/, "ws").replace(/\/$/, "");
    return base + "/ws/session";
  }
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${location.host}/ws/session`;
}

// -- Scenarios (also act as one-tap text prompts for demo) ------------------
const SCENARIOS = [
  { key: "describe", icon: "🪟", label: "前面是什么？", text: "前面是什么?帮我描述一下画面。" },
  { key: "read",     icon: "📖", label: "读这段文字",   text: "帮我读一下画面里的文字。" },
  { key: "find",     icon: "🔍", label: "找东西",       text: "帮我找一下我的钥匙在哪里。" },
  { key: "money",    icon: "💴", label: "这是多少钱",   text: "这张纸币是多少面额?" },
  { key: "menu",     icon: "🍜", label: "读菜单",       text: "帮我读一下这份菜单,有什么推荐?" },
  { key: "med",      icon: "💊", label: "读药盒",       text: "帮我读一下这个药盒的用法用量。" },
  { key: "traffic",  icon: "🚦", label: "红绿灯",       text: "现在红绿灯是什么状态?可以过马路吗?" },
  { key: "transit",  icon: "🚌", label: "公交/地铁",     text: "帮我看一下这是几路车/几号线?" },
  { key: "sign",     icon: "🪧", label: "路牌/门牌",     text: "这个牌子写的什么?" },
  { key: "express",  icon: "📦", label: "快递面单",     text: "帮我看一下这个快递面单上的信息。" },
];

const state = {
  audio: new AudioPipeline(),
  video: new VideoPipeline($("preview")),
  ws: null,
  active: false,
  mode: "default",
  micLevel: 0,
  lastHighFrameAt: 0,
};

// -- UI helpers --------------------------------------------------------------
function setStatus(s, msg) {
  setState(s, msg);
  $("primary-action").dataset.state = s;
}

function appendTranscript(role, text, final) {
  const list = $("captions");
  if (!list) return;
  const last = list.lastElementChild;
  if (last && last.dataset.role === role && last.dataset.final === "false" && !final) {
    last.querySelector(".cap__text").textContent += text;
    return;
  }
  if (last && last.dataset.role === role && last.dataset.final === "false" && final) {
    last.querySelector(".cap__text").textContent = text;
    last.dataset.final = "true";
    return;
  }
  const li = document.createElement("li");
  li.className = `cap cap--${role}`;
  li.dataset.role = role;
  li.dataset.final = final ? "true" : "false";
  li.innerHTML = `<span class="cap__who">${role === "user" ? "你" : "AI"}</span><span class="cap__text">${text}</span>`;
  list.appendChild(li);
  while (list.children.length > 30) list.removeChild(list.firstElementChild);
  list.scrollTop = list.scrollHeight;
}

function setLatencyBadge(metrics) {
  const el = $("latency");
  if (!el) return;
  const fa = metrics.first_audio_ms;
  const tot = metrics.response_total_ms || metrics.total_ms;
  el.textContent = `首句 ${fa ?? "—"}ms · 总 ${tot ?? "—"}ms`;
  el.dataset.tier = fa == null ? "" : fa < 800 ? "good" : fa < 1500 ? "ok" : "slow";
}

function setMode(mode, reason) {
  state.mode = mode;
  const el = $("mode");
  if (el) {
    el.textContent = `模式: ${mode}${reason ? " · " + reason : ""}`;
    el.dataset.mode = mode;
  }
}

function showSafety(category, message) {
  const el = $("safety");
  if (!el) return;
  el.textContent = `⚠️ ${message}`;
  el.hidden = false;
  if (navigator.vibrate) navigator.vibrate([100, 60, 100, 60, 200]);
  clearTimeout(showSafety._t);
  showSafety._t = setTimeout(() => (el.hidden = true), 6000);
}

function showToast(msg) {
  const el = $("toast");
  if (!el) return;
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => (el.hidden = true), 2500);
}

// -- Frame upload ------------------------------------------------------------
async function uploadFrame(quality = "low", purpose = "") {
  const t0 = performance.now();
  const buf = await state.video.grabFrame(quality);
  if (!buf) return;
  state.ws.sendJson({ type: "frame_meta", quality, ts: Date.now(), purpose });
  state.ws.sendBinary(buf);
  console.debug(`frame ${quality} ${buf.byteLength}B in ${(performance.now() - t0).toFixed(0)}ms`);
}

// -- Build scenario chips ----------------------------------------------------
function renderScenarios() {
  const wrap = $("scenarios");
  if (!wrap) return;
  wrap.innerHTML = "";
  for (const s of SCENARIOS) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "chip";
    b.setAttribute("aria-label", s.label);
    b.innerHTML = `<span class="chip__icon" aria-hidden="true">${s.icon}</span><span class="chip__label">${s.label}</span>`;
    b.addEventListener("click", async () => {
      if (!state.active) {
        await startSession();
      }
      // Send a snapshot + a text prompt so the model has fresh context.
      await uploadFrame("low", s.key);
      state.ws.sendJson({ type: "text", text: s.text });
      setStatus("thinking", "思考中…");
    });
    wrap.appendChild(b);
  }
}

// -- Session lifecycle ------------------------------------------------------
async function startSession() {
  if (state.active) return;
  setStatus("listening", "连接中…");

  // Open camera first (silent if denied — vision becomes unavailable).
  try {
    await state.video.start();
  } catch (e) {
    console.warn("camera denied:", e);
    showToast("摄像头未授权,纯语音模式");
  }

  state.ws = new SessionSocket(resolveBackendUrl());
  state.ws.onJson = handleJson;
  state.ws.onBinary = (buf) => state.audio.enqueuePlayback(buf);
  state.ws.onClose = () => {
    state.active = false;
    setStatus("idle", "连接已关闭");
  };
  state.ws.onError = () => {
    setStatus("error", "连接失败");
  };
  await state.ws.connect();
  state.ws.sendJson({ type: "hello", lang: "zh" });

  await state.audio.start({
    onPcm: (buf) => state.ws.sendBinary(buf),
    onLevel: (lvl) => {
      state.micLevel = lvl;
      // Barge-in: user starts talking while assistant is speaking.
      if (lvl > 0.04 && state.audio.isPlaying) {
        state.audio.flushPlayback();
        state.ws.sendJson({ type: "interrupt" });
      }
    },
  });

  state.active = true;
  setStatus("listening", "我在听,你说吧。");

  // Background: refresh a low-res frame every 1.5s so the model always has
  // a recent picture to look at when the user asks.
  state._frameTimer = setInterval(async () => {
    if (state.video.stream) {
      try {
        await uploadFrame("low", "periodic");
      } catch {}
    }
  }, 1500);
}

function endSession() {
  clearInterval(state._frameTimer);
  state.audio.stop();
  state.video.stop();
  if (state.ws) state.ws.close();
  state.active = false;
  setStatus("idle", "已结束");
}

// -- Server event handler ---------------------------------------------------
function handleJson(msg) {
  switch (msg.type) {
    case "ready":
      if (msg.stub) showToast("Stub 模式: 未配置 Azure OpenAI");
      else if (msg.model) showToast(`已连接 · ${msg.model}`);
      break;
    case "state":
      if (msg.state === "speaking") setStatus("speaking", "回答中…");
      else if (msg.state === "thinking") setStatus("thinking", "思考中…");
      else if (msg.state === "listening") setStatus("listening", "在听…");
      else if (msg.state === "idle") setStatus("idle", "我在,等你。");
      break;
    case "transcript":
      appendTranscript(msg.role, msg.text || "", !!msg.final);
      break;
    case "tool":
      // Mostly handled by specific events below; keep for debug.
      console.debug("tool:", msg.name, msg.args);
      break;
    case "mode":
      setMode(msg.mode, msg.reason);
      break;
    case "request_frame":
      uploadFrame(msg.quality || "high", msg.purpose || "");
      showToast(`📷 高清取景 · ${msg.purpose || ""}`);
      break;
    case "quality":
      if (!msg.is_usable) showToast(`📸 ${msg.hint || "请调整角度"}`);
      break;
    case "safety":
      showSafety(msg.category, msg.message);
      break;
    case "latency":
      setLatencyBadge(msg);
      break;
    case "error":
      setStatus("error", msg.message || "出错了");
      showToast(msg.message || "出错");
      break;
  }
}

// -- Boot --------------------------------------------------------------------
async function bootstrap() {
  renderScenarios();
  setStatus("idle", "准备就绪。点击大按钮开始。");

  if ("serviceWorker" in navigator) {
    try {
      await navigator.serviceWorker.register("./service-worker.js");
    } catch {}
  }

  const btn = $("primary-action");
  btn.addEventListener("click", () => {
    if (state.active) {
      // Manual interrupt if speaking, else end.
      if (state.audio.isPlaying) {
        state.audio.flushPlayback();
        state.ws.sendJson({ type: "interrupt" });
        setStatus("listening", "我在听。");
      } else {
        endSession();
      }
    } else {
      startSession().catch((e) => {
        console.error(e);
        setStatus("error", "无法启动: " + (e?.message || e));
      });
    }
  });

  // Triple-click = end session (accessibility shortcut).
  let clicks = 0;
  let clickT;
  btn.addEventListener("click", () => {
    clicks++;
    clearTimeout(clickT);
    clickT = setTimeout(() => (clicks = 0), 600);
    if (clicks >= 3) {
      clicks = 0;
      endSession();
    }
  });
}

bootstrap().catch((err) => {
  console.error(err);
  setStatus("error", "初始化失败:" + (err?.message ?? err));
});
