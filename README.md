# gpt-realtime-2-vision-companion

> 基于 **Azure OpenAI `gpt-realtime-2`** 的实时音视频通话助手 PoC，为视障人群提供"看世界、读文字、找物品、避障提醒"的端到端语音对话体验。
>
> Real-time voice + vision AI companion for blind & low-vision users, powered by Azure OpenAI `gpt-realtime-2`.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Azure](https://img.shields.io/badge/Azure-OpenAI-0078D4?logo=microsoftazure&logoColor=white)](https://learn.microsoft.com/azure/ai-services/openai/)
[![Status](https://img.shields.io/badge/status-PoC-orange)]()

---

## ✨ 项目愿景

类似豆包视频通话，但**为视障用户专门设计**：

- 🎙️ **端到端语音对话**：用户用语音提问，AI 用语音回答，可随时打断
- 👁️ **实时看图理解**：AI 在回答时"看见"用户摄像头当前画面
- ♿ **无障碍优先**：整屏大按钮、唤醒词、触觉与音效反馈、屏幕阅读器友好
- 🚀 **低延迟**：单模型端到端（gpt-realtime-2），首句响应目标 < 2.5s P50
- 🔒 **隐私优先**：默认不持久化音视频，仅脱敏遥测

## 🎯 典型场景

| 场景 | 用户说 | AI 做 |
| --- | --- | --- |
| 识物 | "前面是什么？" | 描述画面主要物品与方位（钟点法） |
| 读文字 | "帮我读一下这个药盒" | 切换 read_text 模式朗读关键信息 |
| 找东西 | "我的钥匙在哪？" | 引导用户转动镜头并指出位置 |
| 导航提醒 | (主动) | "前方一米有台阶，向下三级" |
| 多轮追问 | 中途打断 | 自然衔接、不重复 |

## 🏗️ 架构

```
┌─────────────────────────────────────┐         ┌──────────────────────────────────────┐
│   PWA (Static Web Apps)             │         │  FastAPI Backend (Container Apps)    │
│  - getUserMedia (camera + mic)      │  WSS    │  - /ws/session 长连接                │
│  - AudioWorklet PCM16 录/放         │ ◄────► │  - 双向音频代理到 AOAI Realtime      │
│  - 大按钮 / 唤醒词 / 触觉反馈       │         │  - 用户说话时抽帧注入 conversation   │
│  - 抽帧上传 (按需 low/high res)     │         │  - Function calling 工具实现         │
│  - ARIA / 高对比 / 状态音           │         │  - Managed Identity → AOAI           │
└─────────────────────────────────────┘         └──────────┬───────────────────────────┘
                                                           ▼
                              ┌──────────────────────────────────────────────────┐
                              │ Azure OpenAI: gpt-realtime-2 (语音+vision)       │
                              │ (可选) Azure AI Vision Read API (复杂 OCR 兜底)  │
                              └──────────────────────────────────────────────────┘
```

**模型 fallback 链**：`gpt-realtime-2` → `gpt-realtime` → `gpt-4o-realtime-preview` + 旁路 `gpt-4.1` 看图

## 📦 技术栈

- **前端**：原生 Web (PWA) + AudioWorklet + WebSocket
- **后端**：Python 3.11 + FastAPI + websockets
- **AI**：Azure OpenAI `gpt-realtime-2`
- **基础设施**：Azure Container Apps + Static Web Apps + Bicep + azd
- **可观测性**：Application Insights + OpenTelemetry

## 🚀 快速开始

> 详细步骤将在各阶段实现后补充。

```bash
# 本地后端
cd backend
uv sync   # 或 pip install -e .
cp .env.example .env   # 填入 AOAI endpoint 与 deployment
uvicorn app.main:app --reload --port 8000

# 前端（任意静态服务器）
cd frontend
python -m http.server 5173

# 部署到 Azure（需先 azd auth login）
azd up
```

## ♿ 无障碍设计

| 功能 | 实现 |
| --- | --- |
| 单按钮交互 | 整屏可点 + 长按说话 |
| 语音激活 | 轻量唤醒词 "你好小视" / "Hey assistant" |
| 触觉反馈 | `navigator.vibrate` 区分 listening / thinking / speaking |
| 状态音效 | 每状态独特短音（不依赖视觉） |
| 屏幕阅读器 | 全控件 ARIA label，兼容 VoiceOver / TalkBack |
| 可调语音 | 语速 0.8x–1.5x，多语音 |
| 错误朗读 | 网络/权限错误均 TTS 播报 |

## 🔒 隐私

- 默认**不持久化**任何音视频
- 仅记录脱敏遥测（响应时延、模式切换、错误码）
- WSS 全程 TLS；后端 → AOAI 使用 Managed Identity（无静态密钥）
- 启动时语音明示数据使用范围

## 📝 License

[MIT](./LICENSE)

## 🙏 致谢

- Azure OpenAI Service — `gpt-realtime-2`
- 灵感来源：豆包视频通话、Be My Eyes、Seeing AI
