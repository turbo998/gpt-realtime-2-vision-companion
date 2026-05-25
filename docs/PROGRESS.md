# Progress & Status

> 项目阶段性快照。供"未来的我/你"接着开发用。
>
> 完整设计请看 [`./plan.md`](./plan.md)；总体架构 [`./architecture.md`](./architecture.md)。

最后更新：2026-05-25

---

## ✅ 已完成（3 / 13）

### 1. `create-github-repo`
- 创建 public repo: <https://github.com/turbo998/gpt-realtime-2-vision-companion>
- 本地 git init、`.gitignore` (Python+Node+Azure)、`LICENSE` (MIT)、`README.md`
- 初始 commit `0f3c46a` 已 push

### 2. `scaffold`
- 完整目录树：`backend/` `frontend/` `infra/` `docs/` `.vscode/` `azure.yaml` `.editorconfig`
- 后端：FastAPI 应用（`app/main.py`）、pydantic-settings 配置（`app/config.py`）、`Dockerfile`、`.env.example`、`pyproject.toml`
- 后端占位模块：`ws_session.py` / `realtime_client.py` / `tools.py` / `prompts.py` / `telemetry.py`
- 前端 PWA：`index.html`、`manifest.webmanifest`、`service-worker.js`、`styles/main.css`、模块占位（`app.js` / `audio.js` / `video.js` / `ws.js` / `a11y.js` / `wake-word.js`）
- 基建：`infra/main.bicep`（入口）+ 4 个模块占位 + `main.parameters.json` + `azure.yaml`（azd）
- 文档：`architecture.md` / `demo-script.md` / `accessibility.md` / `plan.md`

### 3. `backend-skeleton`
- FastAPI 启动正常（`uvicorn app.main:app` → `/health` 返回 `{"status":"ok","version":"0.1.0"}`）
- WebSocket `/ws/session` echo 通了（含 `hello` 握手 + `echo` 消息）
- pytest 2 个用例（`test_health_ok` + `test_ws_session_handshake`）100% 通过
- pydantic-settings 读 `.env` 验证 OK

#### 验证步骤
```bash
cd backend
pip install -e ".[dev]" --only-binary=:all:    # win-arm64 必加 --only-binary
pytest -q                                       # 2 passed
uvicorn app.main:app --reload --port 8000      # 然后访问 /health
```

---

## ⏳ 待办（10 / 13） — 推荐顺序

| # | Todo ID | 简述 | 依赖 |
| --- | --- | --- | --- |
| 4 | `realtime-integration` | 接通 Azure OpenAI Realtime WSS（含 DefaultAzureCredential、session.update、双向事件） | backend-skeleton ✅ |
| 5 | `frontend-audio` | AudioWorklet 录 PCM16/24k + 流式播放 + 打断（response.cancel） | backend-skeleton ✅ |
| 6 | `vision-injection` | 前端 1FPS 帧缓存 + 用户开口时上传 low-res；后端注入 `conversation.item.create` | 4 + 5 |
| 7 | `accessibility` | 状态音效、唤醒词、ARIA 完善、双/三指手势、TalkBack/VoiceOver 实测 | 5 |
| 8 | `prompt-and-tools` | 系统提示词调优 + tools handler 接线（set_mode / request_high_res_frame / frame_quality_check） | 6 |
| 9 | `infra-bicep` | 4 个模块的真实实现 + azd 一键起 | scaffold ✅ |
| 10 | `observability` | App Insights + OpenTelemetry + 自定义 metric（first_audio_latency_ms 等） | backend-skeleton ✅ |
| 11 | `deploy-and-verify` | `azd up` → 手机浏览器实测 | 7 + 8 + 9 + 10 |
| 12 | `demo-script` | 5 个场景台词 + 兜底 + 演示 checklist | 11 |
| 13 | `ocr-augment` (可选) | Azure AI Vision Read API 复杂 OCR 兜底 | 8 |

---

## 🔧 接着开发：实用提示

### 环境准备
- Python 3.11+（本仓库使用 3.12 验证过）
- Node 不强制（前端是纯 JS，任意静态服务器即可）
- Azure CLI + azd（部署阶段才需要）

### Win-ARM64 注意事项
- `uvicorn[standard]` 的 `httptools` 没有 ARM64 wheel；本仓库已改用纯 `uvicorn`（仍可走 `websockets` 库实现 WS）
- 安装时加 `--only-binary=:all:` 避免源码编译

### 下一步具体行动建议（`realtime-integration`）
1. 在 `backend/app/realtime_client.py` 实现：
   - `connect(deployment, api_version)` → 拼 `wss://{endpoint}/openai/realtime?deployment=...&api-version=...`
   - 认证：`azure.identity.DefaultAzureCredential().get_token("https://cognitiveservices.azure.com/.default")` → `Authorization: Bearer ...`；API key fallback `api-key` header
   - `session.update`：`modalities=["text","audio"]`、`voice="alloy"`（或新声音）、`input_audio_format="pcm16"`、`output_audio_format="pcm16"`、`input_audio_transcription={"model":"whisper-1"}`、`turn_detection={"type":"server_vad"}`、`tools` 来自 `app.tools.TOOLS`
   - 事件分发器（asyncio.Queue 给 ws_session 消费）
2. 改写 `backend/app/ws_session.py`：建立 `RealtimeClient`，把客户端二进制音频转成 `input_audio_buffer.append`；把模型 `response.audio.delta` 转回客户端
3. 加测试：mock Realtime 端点验证转发逻辑

### 模型 fallback 策略
代码里准备这个顺序：
1. `AZURE_OPENAI_REALTIME_DEPLOYMENT`（默认 `gpt-realtime-2`）
2. 收到 4xx 时 fallback 到 `AZURE_OPENAI_REALTIME_FALLBACK_DEPLOYMENT`（默认 `gpt-4o-realtime-preview`）
3. 都不行就走 stub：固定回 "服务暂不可用，请稍后再试"（保证 demo 不会黑屏）

### 区域建议
gpt-realtime 系列优先：
- East US 2
- Sweden Central
- (查最新文档确认 gpt-realtime-2 的发布区域)

---

## 📂 当前仓库结构

```
gpt-realtime-2-vision-companion/
├── README.md
├── LICENSE
├── .gitignore
├── .editorconfig
├── azure.yaml
├── .vscode/extensions.json
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── .env.example
│   ├── README.md
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            ✅ 可运行
│   │   ├── config.py          ✅ 完整
│   │   ├── ws_session.py      🟡 echo 占位
│   │   ├── realtime_client.py 🟡 接口骨架
│   │   ├── tools.py           🟡 schema 就绪，handler 待接
│   │   ├── prompts.py         ✅ 中英文系统提示词
│   │   └── telemetry.py       🟡 no-op 占位
│   └── tests/
│       └── test_health.py     ✅ 2 passing
├── frontend/
│   ├── index.html             ✅ 无障碍 shell
│   ├── manifest.webmanifest   ✅
│   ├── service-worker.js      ✅
│   ├── README.md
│   ├── styles/main.css        ✅ 大按钮 + 状态色 + 脉冲
│   ├── public/                (待放 icon-192/512)
│   └── src/
│       ├── app.js             🟡 启动 + 状态切换占位
│       ├── audio.js           🟡 待实现
│       ├── video.js           🟡 待实现
│       ├── ws.js              🟡 待实现
│       ├── a11y.js            ✅ 状态机 + 振动
│       └── wake-word.js       🟡 待实现
├── infra/
│   ├── main.bicep             🟡 入口 + TODO 标记
│   ├── main.parameters.json   ✅
│   └── modules/
│       ├── openai.bicep            🟡 待实现
│       ├── container-app.bicep     🟡 待实现
│       ├── static-web-app.bicep    🟡 待实现
│       └── monitoring.bicep        🟡 待实现
└── docs/
    ├── plan.md                ✅ 完整设计（13 todo + 风险 + 验收）
    ├── architecture.md        ✅
    ├── demo-script.md         ✅
    ├── accessibility.md       ✅
    └── PROGRESS.md            ← 本文
```

图例：✅ 完整 · 🟡 占位/骨架（含 TODO 注释指向哪个 todo 实现）

---

## 🧭 已确认的关键决策

| 项 | 决策 |
| --- | --- |
| 前端载体 | Web PWA |
| 交互模式 | 语音 Q&A + 模型主动安全提醒 |
| 模型链路 | gpt-realtime-2 端到端（语音+vision），fallback gpt-4o-realtime-preview |
| 部署 | Azure Container Apps（后端）+ Static Web Apps（前端） |
| 后端语言 | Python 3.11 + FastAPI + websockets |
| 认证 | User-Assigned Managed Identity（Container App → AOAI） |
| 隐私 | 默认不持久化音视频 |

---

## 📌 Commits

| Hash | 内容 |
| --- | --- |
| `0f3c46a` | chore: initial scaffold with README, LICENSE, gitignore |
| `5bb5021` | feat: scaffold backend (FastAPI+WS), frontend (PWA), infra (Bicep) and docs |
