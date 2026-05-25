# Backend — FastAPI WebSocket Service

代理客户端音频 ↔ Azure OpenAI `gpt-realtime-2`，并在用户说话开始时注入最近一帧图像。

## 本地运行

```bash
pip install -e ".[dev]"
cp .env.example .env   # 填入 AZURE_OPENAI_ENDPOINT 等
uvicorn app.main:app --reload --port 8000
```

http://localhost:8000/health → `{"status":"ok"}`

## 测试

```bash
pytest
```

## 模块速览

| 文件 | 职责 |
| --- | --- |
| `app/main.py` | FastAPI 入口、路由注册、生命周期 |
| `app/config.py` | pydantic-settings 配置 |
| `app/ws_session.py` | `/ws/session` WebSocket 端点，编排一次会话 |
| `app/realtime_client.py` | 与 Azure OpenAI Realtime API 的连接与事件转换 |
| `app/tools.py` | Function calling 工具（模式切换、抽帧请求等） |
| `app/prompts.py` | 视障助理系统提示词 |
| `app/telemetry.py` | OpenTelemetry / App Insights 初始化 |
