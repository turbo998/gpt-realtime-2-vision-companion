# PoC: 视障人群实时音视频通话助手 (类豆包视频通话)

> **GitHub Repo**: `turbo998/gpt-realtime-2-vision-companion` (public)
> **本地路径**: `C:\Users\qichen2\gpt-realtime-2-vision-companion`

## 1. 问题与目标
为视障用户提供一个"实时视频通话式"AI 助理：
- 用户语音提问（"前面是什么？""这个牌子写了啥？"）
- AI 端到端语音回答，并基于用户当前摄像头画面做出回答
- 体验接近自然对话：可打断、低延迟、连续多轮
- 全程无障碍优先（大按钮、语音激活、屏幕阅读器友好、状态音效）

## 2. 技术决策（已与用户确认）
| 决策项 | 选择 |
| --- | --- |
| 前端载体 | Web PWA（手机浏览器可用，调用 getUserMedia 摄像头+麦克风） |
| 交互模式 | 用户语音 Q&A 为主，AI 结合当前画面语音回答 |
| 模型链路 | **方案1：GPT Realtime 端到端**（语音入 → 语音出）+ 同一多模态模型抽帧看图 |
| 部署 | Azure Container Apps（后端 WebSocket）+ Azure Static Web Apps（前端 PWA） |
| 后端语言 | Python（FastAPI + WebSocket） |
| 主模型 | Azure OpenAI **`gpt-realtime-2`**（最新一代 realtime 模型，端到端语音+原生 vision 输入；如区域不可用则 fallback 到 `gpt-realtime` / `gpt-4o-realtime-preview` + 旁路 `gpt-4.1` 看图） |

## 3. 整体架构

```
┌─────────────────────────────────────┐         ┌──────────────────────────────────────┐
│   PWA (Static Web Apps)             │         │  FastAPI Backend (Container Apps)    │
│  - getUserMedia (camera+mic)        │  WSS    │  - /ws/session 长连接                │
│  - 大按钮 / 语音激活 / 触觉反馈      │ ◄────► │  - 转发用户音频到 Azure OpenAI       │
│  - PCM16 音频流播放 (打断支持)      │         │  - 抽帧注入 Realtime conversation    │
│  - 抽帧上传 (按需)                  │         │  - 工具调用 (OCR 增强 / 模式切换)    │
│  - ARIA / 高对比 / 系统状态音       │         │  - Managed Identity → AOAI           │
└─────────────────────────────────────┘         └──────────┬───────────────────────────┘
                                                           │
                                                           ▼
                              ┌──────────────────────────────────────────────────┐
                              │ Azure OpenAI                                     │
                              │  - gpt-realtime-2 (语音入/出 + 原生 vision)     │
                              │  - (可选) Azure AI Vision Read API (OCR 增强)   │
                              └──────────────────────────────────────────────────┘
```

### 数据流（一次问答）
1. 用户长按或唤醒词激活，前端开始流式上传麦克风 PCM16 音频 → 后端
2. 后端把音频 chunk 转发到 Azure OpenAI Realtime WebSocket
3. Realtime 服务 server VAD 检测到说话结束 → 触发 `response.create`
4. 触发前，后端从前端拉取**最近一帧 JPEG**（low-res），以 `input_image` 方式注入 conversation
5. 模型基于"语音问题 + 当前画面"生成语音回答，PCM 流回前端
6. 前端低延迟播放；用户开口即打断（前端检测到用户音量后发送 `response.cancel`）

## 4. 关键设计点

### 4.1 视障无障碍 (Accessibility First)
- **单按钮交互**：整屏可点；同时支持唤醒词 "你好小视" / "Hey assistant" 激活
- **触觉反馈**：navigator.vibrate 在 listening / thinking / speaking 状态切换时给不同震动
- **状态音效**：每个状态有独特短音（不依赖视觉提示）
- **屏幕阅读器**：所有控件 ARIA label，配合 VoiceOver / TalkBack
- **声音可配置**：语速 0.8x-1.5x，多语音可选，默认中文女声温和
- **错误用语音通报**：网络断开、麦克风权限拒绝等都用 TTS 朗读

### 4.2 模型 Prompt 设计（system message）
- 角色：贴心、简洁的视障助理
- 回答风格：**先一句话给结论，再视情况展开**；避免冗长
- 描述方位用钟点法（"在你前方约2米，10点钟方向"）
- 文字识别：完整朗读但避免重复
- 不确定就明说"画面比较模糊，建议靠近些"
- 安全：识别到危险情况（车辆/楼梯/障碍）主动提醒

### 4.3 专项模式（Function Calling 工具）
模型可调用以下工具切换专项行为：
- `set_mode("read_text" | "describe_scene" | "find_object" | "navigate" | "default")`
- `request_high_res_frame()`：触发前端发送高分辨率帧（默认 low-res 省带宽）
- `call_emergency_contact()`：未来扩展（占位符）

### 4.4 抽帧策略
- 默认前端按 1 FPS 缓存最近帧（仅本地，不上传）
- 用户说话开始时上传一帧 low-res（640x480 JPEG q70 ~30KB）
- 模型主动调用 `request_high_res_frame` 时上传 1280x960 q85
- 节省 token 与带宽，避免持续传图

### 4.5 隐私与安全
- 默认**不持久化**音视频，会话内存中处理完即丢
- 仅记录脱敏遥测（响应时延、模式切换次数、错误码）到 Application Insights
- 前端启动时明确语音提示"将使用摄像头与麦克风，仅会话内使用"
- WSS 全程 TLS；后端→AOAI 使用 Managed Identity，无静态密钥

### 4.6 打断与回合管理
- 使用 Realtime 的 server VAD (`turn_detection: server_vad`)
- 前端检测到用户声音超阈值且模型正在说话 → 发送 `response.cancel` 立即停止 TTS
- 真正模拟"插话"自然对话

## 5. Azure 资源清单 (IaC: Bicep + azd)
| 资源 | 用途 |
| --- | --- |
| Resource Group | 容器 |
| Azure OpenAI | `gpt-realtime-2` deployment（必要时多区域，因 realtime 区域有限） |
| Container Apps Environment | 后端运行环境 |
| Container App (backend) | FastAPI 服务，min=1 (避免冷启动) max=10，HTTP+WebSocket |
| Container Registry | 镜像仓库 |
| Static Web Apps | 前端 PWA 托管 + 自动 CDN |
| User-Assigned Managed Identity | Container App 访问 AOAI |
| Key Vault | 兜底密钥存储（首选 MI） |
| Application Insights + Log Analytics | 遥测、日志、追踪（含 OpenTelemetry） |
| (可选) Azure AI Vision | Read API 高精度 OCR 兜底 |

## 6. 目录结构（计划）
```
gpt-realtime-2-vision-companion/
├── azure.yaml                       # azd 配置
├── infra/                           # Bicep
│   ├── main.bicep
│   ├── modules/
│   │   ├── openai.bicep
│   │   ├── container-app.bicep
│   │   ├── static-web-app.bicep
│   │   └── monitoring.bicep
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py                  # FastAPI 入口
│   │   ├── ws_session.py            # WebSocket 会话编排
│   │   ├── realtime_client.py       # Azure OpenAI Realtime 代理
│   │   ├── tools.py                 # function calling 工具实现
│   │   ├── prompts.py               # 系统提示词
│   │   ├── config.py                # 配置（pydantic-settings）
│   │   └── telemetry.py             # OpenTelemetry / App Insights
│   └── tests/
├── frontend/
│   ├── index.html                   # PWA 入口
│   ├── manifest.webmanifest
│   ├── service-worker.js
│   ├── src/
│   │   ├── app.js                   # 状态机
│   │   ├── audio.js                 # PCM16 录音 + 播放 (AudioWorklet)
│   │   ├── video.js                 # 摄像头 + 抽帧
│   │   ├── ws.js                    # WebSocket 协议
│   │   ├── a11y.js                  # 无障碍 (触觉/音效/ARIA 状态)
│   │   └── wake-word.js             # 唤醒词（轻量本地）
│   └── styles/
├── docs/
│   ├── architecture.md
│   ├── demo-script.md               # 演示话术与场景
│   └── accessibility.md
└── README.md
```

## 7. 实施阶段（Todo 概览，详情见 SQL）
0. **create-github-repo**：使用 `gh repo create turbo998/gpt-realtime-2-vision-companion --public` 在 GitHub 新建 public repo，本地 git init + 关联 remote
1. **scaffold**：创建仓库骨架、azure.yaml、目录结构、README、LICENSE (MIT)、.gitignore（Python+Node）
2. **backend-skeleton**：FastAPI + WebSocket echo 服务，能本地运行
3. **realtime-integration**：后端接入 Azure OpenAI Realtime，端到端语音对话跑通（无图）
4. **frontend-audio**：前端 PWA，录音/播放/打断闭环，能与后端语音对话
5. **vision-injection**：前端抽帧 + 后端把帧注入 Realtime conversation，跑通"看图问答"
6. **accessibility**：无障碍 UI（大按钮、触觉、状态音、ARIA、唤醒词）
7. **prompt-and-tools**：系统提示词 + function calling 工具（专项模式、高清帧请求）
8. **infra-bicep**：Bicep IaC，azd 一键部署
9. **observability**：App Insights、OpenTelemetry、关键指标
10. **deploy-and-verify**：部署到 Azure，端到端验证
11. **demo-script**：演示脚本（4-5 个典型场景：识物、读文字、导航提示、找东西、危险提醒）
12. **(可选) ocr-augment**：复杂文字场景 fallback 到 Azure AI Vision Read API

## 8. 风险与备选
| 风险 | 缓解 |
| --- | --- |
| `gpt-realtime-2` 区域/订阅可用性受限 | 部署到 East US 2 / Sweden Central；自动 fallback `gpt-realtime` → `gpt-4o-realtime-preview` |
| Realtime vision 在 v2 上行为有差异 | 抽象 `RealtimeClient` 接口，支持版本切换；退化方案：抽帧走 `gpt-4.1` 文本流式，关键句喂入 Realtime "user message" 让其朗读 |
| Container Apps 冷启动影响首句延迟 | min replicas=1，启用 startup probe 预热 |
| 浏览器音频权限/HTTPS 限制 | Static Web Apps 天然 HTTPS；本地开发用 mkcert |
| 视障用户难以"看到"摄像头是否对准目标 | 增加 `frame_quality_check`：模型先评估画面清晰度/对焦，主动指导用户调整角度 |
| Token / 时延成本 | low-res 抽帧默认，高清按需；前端 1 FPS 缓存避免持续上传 |

## 9. 演示脚本预览（demo-script.md 草稿）
1. **识物**：摄像头对桌面物品 → "前面有什么？" → AI："桌上有一杯水、一本书和一副眼镜"
2. **读文字**：对准药盒 → "帮我读一下" → AI 自动切 read_text 模式朗读关键信息
3. **找东西**：举起手机环顾 → "我的钥匙在哪？" → AI："右前方桌面靠近笔记本电脑的位置"
4. **导航提醒**：行走中 → AI 主动："前方一米有台阶，向下三级"
5. **多轮对话**：用户中途打断追问细节 → 自然衔接

## 10. 验收标准
- [ ] 本地能跑通端到端语音对话（含看图）
- [ ] 首句响应延迟 < 2.5s (P50)
- [ ] 用户可在 AI 说话时打断
- [ ] 部署到 Azure 后用手机浏览器可直接访问演示
- [ ] 通过 VoiceOver / TalkBack 单手可用
- [ ] 5 个 demo 场景全部成功
