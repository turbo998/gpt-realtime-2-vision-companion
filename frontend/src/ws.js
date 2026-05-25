// WebSocket protocol wrapper: text frames are JSON; binary frames are
// either raw PCM16 chunks (mic) / JPEG (frames) outbound, and PCM16
// playback chunks inbound.

export class SessionSocket {
  constructor(url) {
    this.url = url;
    this.ws = null;
    this.onJson = null; // (obj) => void
    this.onBinary = null; // (ArrayBuffer) => void
    this.onOpen = null;
    this.onClose = null;
    this.onError = null;
  }

  connect() {
    return new Promise((resolve, reject) => {
      const ws = new WebSocket(this.url);
      ws.binaryType = "arraybuffer";
      ws.onopen = () => {
        this.ws = ws;
        if (this.onOpen) this.onOpen();
        resolve();
      };
      ws.onmessage = (ev) => {
        if (typeof ev.data === "string") {
          try {
            const obj = JSON.parse(ev.data);
            if (this.onJson) this.onJson(obj);
          } catch (e) {
            console.warn("bad json", e, ev.data);
          }
        } else if (ev.data instanceof ArrayBuffer) {
          if (this.onBinary) this.onBinary(ev.data);
        }
      };
      ws.onclose = (e) => {
        if (this.onClose) this.onClose(e);
      };
      ws.onerror = (e) => {
        if (this.onError) this.onError(e);
        if (ws.readyState !== WebSocket.OPEN) reject(e);
      };
    });
  }

  sendJson(obj) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(obj));
    }
  }

  sendBinary(buf) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(buf);
    }
  }

  close() {
    try {
      this.ws && this.ws.close();
    } catch {}
    this.ws = null;
  }
}
