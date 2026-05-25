// App entry. Wires together audio / video / ws / a11y modules.
// Real logic implemented in subsequent todos.
import { setState } from "./a11y.js";

const button = document.getElementById("primary-action");

async function bootstrap() {
  setState("idle", "准备就绪。点击或长按说话。");

  if ("serviceWorker" in navigator) {
    try {
      await navigator.serviceWorker.register("./service-worker.js");
    } catch (err) {
      console.warn("SW registration failed:", err);
    }
  }

  button.addEventListener("click", () => {
    setState("listening", "正在聆听...");
    // TODO: start mic + ws session (frontend-audio todo)
    setTimeout(() => setState("idle", "（占位）下一步实现录音流。"), 1200);
  });
}

bootstrap().catch((err) => {
  console.error(err);
  setState("error", "初始化失败：" + (err?.message ?? err));
});
