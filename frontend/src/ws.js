// WebSocket protocol wrapper between PWA and FastAPI backend.
// Real implementation in `frontend-audio` / `vision-injection`.
export class SessionSocket {
  constructor(url) {
    this.url = url;
    this.ws = null;
  }
  connect() {
    throw new Error("not implemented yet");
  }
  send(_msg) {}
  close() {}
}
