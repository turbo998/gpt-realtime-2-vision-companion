# Frontend — Vision Companion PWA

无障碍优先的 PWA：调用摄像头与麦克风，通过 WebSocket 与后端进行实时语音对话。

## 本地预览

任意静态服务器即可：

```bash
# Python
python -m http.server 5173

# 或 npx serve
npx serve -l 5173 .
```

打开 http://localhost:5173

> ⚠️ getUserMedia 需要 HTTPS（localhost 例外）。手机测试建议用 mkcert 起本地 HTTPS。

## 文件结构

```
frontend/
├── index.html
├── manifest.webmanifest
├── service-worker.js
├── styles/main.css
├── public/         # icons (添加 192/512 png 后再启用 manifest)
└── src/
    ├── app.js      # 入口，状态机
    ├── audio.js    # AudioWorklet PCM16 录/放
    ├── video.js    # 摄像头 + 抽帧
    ├── ws.js       # WebSocket 协议
    ├── a11y.js     # 无障碍状态机（视觉/触觉/音效）
    └── wake-word.js # 唤醒词
```

## 配置后端地址

`src/ws.js` 默认连接 `ws(s)://<host>/ws/session`，与前端同源。本地开发时请通过反向代理或在 `app.js` 中改写 URL 指向 `ws://localhost:8000/ws/session`。
