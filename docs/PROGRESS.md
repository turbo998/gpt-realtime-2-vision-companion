# Progress & Status

> 项目阶段性快照。供"未来的我/你"接着开发用。
>
> 完整设计请看 [`./plan.md`](./plan.md)；端到端延迟说明 [`./LATENCY.md`](./LATENCY.md)；演示脚本 [`./demo-script.md`](./demo-script.md)。

最后更新：2026-05-25（v0.2 — 端到端 demo 可跑）

---

## ✅ 已完成（13 / 13）

### 1. `create-github-repo`
Public repo: <https://github.com/turbo998/gpt-realtime-2-vision-companion>，MIT License。

### 2. `scaffold`
完整目录树：`backend/` `frontend/` `infra/` `docs/` + `azure.yaml`。

### 3. `backend-skeleton`
FastAPI + pydantic-settings + Dockerfile + pytest 全跑通。

### 4. `realtime-client` ✅
- `backend/app/realtime_client.py`：完整 Azure OpenAI Realtime WSS 客户端
- 双鉴权：`DefaultAzureCredential` Bearer token → `api-key` fallback
- `session.update` 注入 `instructions` / `tools` / `voice` / `input_audio_format=pcm16`
- 事件迭代器：`async for event in client.events()`
- 方法：`send_audio_chunk` / `send_text` / `send_image_jpeg` / `cancel_response` / `commit_user`

### 5. `ws-session` ✅
- `backend/app/ws_session.py`：前后端协议桥接 + 状态机
- 协议文档化（文件头注释）：JSON 文本帧 + 原始二进制（PCM16 / JPEG）
- `frame_meta` 文本帧前置 → 二进制 JPEG 帧
- 麦克风 PCM16 24kHz mono → AOAI `input_audio_buffer.append`
- AOAI `response.output_audio.delta` → 前端原始二进制播放
- `interrupt` → `response.cancel` + 前端立即 flush 播放队列
- 转写流（user + assistant，带 final 标志）
- Tool call → 翻译为 `mode` / `request_frame` / `safety` 控制帧
- 首句音频延迟埋点（`vc.first_audio_ms`）

### 6. `prompts-and-tools` ✅
- `prompts.py`：`SYSTEM_PROMPT_ZH` — 角色"视觉伙伴"、安全/简短/口语化规则
- `tools.py`：10+ 场景对应的 function schema
  - `set_mode(describe|read_text|find_object|navigation|currency|menu|medicine|transit|sign|shipping)`
  - `request_high_res_frame(purpose)`
  - `frame_quality_check(is_usable, hint)`
  - `safety_alert(category, message)` — 红绿灯/车辆/障碍物
  - `privacy_redact(level)` — 隐私信息（快递面单单号等）

### 7. `frontend-audio` ✅
- `audio.js` + `worklet/capture-processor.js`：AudioWorklet 双向 PCM16 24kHz
- 采集端 40ms flush，原生重采样从 48kHz 降到 24kHz
- 播放端 `AudioBufferSourceNode` 排队，零拷贝二进制接收
- VU 表 → 触发打断检测
- `flushPlayback()` 立即清空待播队列

### 8. `frontend-video` ✅
- `video.js`：摄像头流 + `OffscreenCanvas` 抽帧
- `grabFrame('low')` → 640×480 JPEG q=0.7
- `grabFrame('high')` → 1280×960 JPEG q=0.85
- 后置摄像头优先（`facingMode: environment`）

### 9. `frontend-app` ✅
- `ws.js`：JSON + 二进制双轨 WebSocket 封装
- `app.js`：完整编排
  - 10 个一键场景芯片
  - 状态机：idle / listening / thinking / speaking / error
  - 后台每 1.5s 自动低清取景（预热）
  - 打断检测（VU > 0.04 + isPlaying）
  - 延迟徽章实时更新（绿/黄/红三档）
  - Safety alert 横幅 + 振动
  - Triple-click 大按钮 = 结束会话（无障碍）

### 10. `frontend-html-css` ✅
- `index.html`：无障碍优先，跳过链接、ARIA live、72px 主按钮
- `main.css`：暗色护眼、状态色映射主按钮、自适应布局、`prefers-reduced-motion` 支持
- `manifest.webmanifest` + 简版 service worker（PWA 可安装）

### 11. `infra-bicep` ✅
- `infra/main.bicep`：完整模块编排
- `modules/openai.bicep`：Cognitive Services + gpt-realtime-2 GlobalStandard
- `modules/monitoring.bicep`：Log Analytics + App Insights（workspace-based）
- `modules/container-app.bicep`：ACR + UAMI + Managed Env + Container App
  - 角色：`Cognitive Services OpenAI User` + `AcrPull`
  - 环境变量自动注入：`AZURE_OPENAI_ENDPOINT` / `AZURE_CLIENT_ID` / `APPLICATIONINSIGHTS_CONNECTION_STRING`
- `modules/static-web-app.bicep`：Free 套餐，可选 GitHub CI
- Outputs：`BACKEND_URL` / `FRONTEND_URL` / `AZURE_OPENAI_ENDPOINT` / `APPLICATIONINSIGHTS_CONNECTION_STRING`

### 12. `telemetry-appi` ✅
- `telemetry.py`：可选 Azure Monitor OTel 接入
- 自定义指标：`vc.first_audio_ms` / `vc.response_total_ms` / `vc.frame_bytes` / `vc.tool_calls`
- **不发送原始音频/图像字节**（隐私）

### 13. `docs` ✅
- `LATENCY.md`：延迟预算 + 测量 + KQL
- `demo-script.md`：10 个可演示场景 + 演示节奏 + Checklist
- `PROGRESS.md`：本文件

---

## 🚀 一键部署

```bash
# 1. 部署 Azure 资源
azd up
# → 选择订阅 / region（建议 eastus2 / swedencentral / japaneast 之一，看 gpt-realtime-2 哪里上）

# 2. 构建并推送后端镜像
ACR=$(azd env get-value ACR_LOGIN_SERVER)
docker build -t $ACR/vision-companion-backend:v1 backend/
az acr login --name ${ACR%%.*}
docker push $ACR/vision-companion-backend:v1
# 重新部署，让 Container App 拉新镜像
azd deploy

# 3. 部署前端到 SWA
swa deploy frontend --env production
```

## 🧪 本地开发

```bash
# 后端
cd backend
pip install -e ".[dev]"
cp .env.example .env  # 填 AZURE_OPENAI_ENDPOINT 等
uvicorn app.main:app --reload --port 8000

# 前端（另开终端）
cd frontend
python -m http.server 5173
# 浏览器开 http://localhost:5173?backend=ws://localhost:8000
```

无 Azure 配置时后端进入 **stub 模式**，前端依然能跑（看到"Stub 模式"toast），适合做 UI 联调。

## 📍 下一步建议（v0.3+）

- [ ] Realtime VAD：服务端 `turn_detection: server_vad` 改 `none` 由前端控制以降延迟
- [ ] Wake word：浏览器端 picovoice/porcupine 整合（`wake-word.js` 占位已存在）
- [ ] iOS Safari AudioContext unlock 测试
- [ ] 中国大陆区接入：等 gpt-realtime-2 上中国区 / Sovereign Cloud
- [ ] E2E 自动化：Playwright 模拟麦克风 + 摄像头流
- [ ] 主动场景：基于持续帧流的"前方台阶""红绿灯变绿"主动提醒（需要 background analysis）
