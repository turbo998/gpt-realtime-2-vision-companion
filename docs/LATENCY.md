# 端到端延迟（LATENCY）

视觉伙伴的核心承诺是 **"低延迟、可打断"** 的多模态实时交互。下面分解延迟预算、测量方法和优化点。

## 关键指标

| 名称 | 含义 | 目标 | 测量点 |
|---|---|---|---|
| **首句音频延迟** `first_audio_ms` | 用户结束说话 → 助手第一段 PCM16 音频抵达前端扬声器 | < 800 ms | `ws_session.py` 记录 `user.commit` 时间戳 → 首个 `response.output_audio.delta` 时间戳 |
| **回答总时长** `response_total_ms` | 首段音频 → `response.done` | 受语义长度影响 | `ws_session.py` |
| **打断响应时长** `barge_in_ms` | 前端检测用户开口 → 助手停止播放 | < 200 ms | 前端 `audio.flushPlayback()` + `response.cancel` 发出 |
| **抽帧延迟** `frame_capture_ms` | `OffscreenCanvas` → JPEG ArrayBuffer | < 80 ms (低清) / < 200 ms (高清) | `app.js: uploadFrame` `performance.now()` 包裹 |
| **WSS RTT** | 浏览器 ↔ Container App ping 往返 | < 60 ms（同区域）| `state.ws` 周期 ping（TODO） |
| **AOAI 首 token** | 后端 `session.update` → 第一个 server event | < 400 ms | `realtime_client.events()` 第一帧戳 |

## 延迟预算（典型 4G/Wi-Fi · 同区域）

```
用户说完
   │ 50ms   端侧 VAD（浏览器抓取最后一段 PCM）
   │ 30ms   前端 → 后端 WSS（同区域）
   │ 30ms   后端 → AOAI WSS
   │ 250ms  AOAI 模型反应 + 首 token
   │ 30ms   AOAI → 后端
   │ 30ms   后端 → 前端
   │ 20ms   AudioBuffer schedule
   ▼
首段语音播出  ≈ 440ms   ✅
```

异地（跨大区）/弱网下，可飙升到 1.2–1.8s。Static Web App 与 Container App 务必同区。

## 已落地的优化

1. **音频用 PCM16 24kHz 原始二进制帧**，不走 base64/JSON 包装 → 节省 33% 字节、零序列化。
2. **AudioWorklet 双向**：采集端 40ms 一帧 flush，播放端用 `AudioBufferSourceNode` 排队，避免 ScriptProcessor 的主线程抖动。
3. **打断零延迟**：浏览器麦克风 VU > 0.04 触发 `flushPlayback()` + 服务端 `response.cancel`，扬声器立刻静音。
4. **预热低清帧**：每 1.5s 自动发一帧 640×480 JPEG，用户提问时模型已经"看过"画面 → 首句延迟少了一次取景往返。
5. **按需高清帧**：模型通过 function call `request_high_res_frame` 拉 1280×960 JPEG，仅在 OCR/找小物时触发。
6. **后端在 Azure Container App 与 OpenAI 同区域**（Bicep 默认 `resourceGroup().location`）。
7. **Telemetry 只发指标不发原始字节**：`telemetry.py` 仅记录 ms/字节数/事件计数。

## 测量方法

### 本地
```bash
cd backend && pytest -q
# 启动后端
uvicorn app.main:app --reload --port 8000
# 启动前端
cd ../frontend && python -m http.server 5173
# 浏览器开 http://localhost:5173?backend=ws://localhost:8000
# 控制台观察 console.debug 输出 + 右上角"首句 / 总"徽章
```

### Azure
- App Insights → Live Metrics → 自定义指标 `vc.first_audio_ms` 直方图
- KQL：
  ```kql
  customMetrics
  | where name == "vc.first_audio_ms"
  | summarize p50=percentile(value,50), p95=percentile(value,95) by bin(timestamp, 5m)
  ```

## 已知瓶颈 / 下一步

- [ ] 跨大区延迟（中国大陆 ↔ 海外 AOAI）：考虑 Azure Front Door 边缘汇聚 + 中国区 AOAI（待 `gpt-realtime-2` 上中国区）
- [ ] WSS RTT 主动探针 + UI 显示
- [ ] 弱网降级：若 `first_audio_ms` > 1500ms 连续 3 次，自动降帧率 + 关高清取景
- [ ] HTTP/3 与 QUIC：等 Container Apps GA 后切换
