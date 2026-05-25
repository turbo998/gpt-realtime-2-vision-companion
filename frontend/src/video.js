// Camera capture + low/high-res frame extraction. Implemented in `vision-injection` todo.
export class VideoPipeline {
  constructor() {
    this.stream = null;
  }
  async start() {
    throw new Error("not implemented yet");
  }
  async grabFrame(_quality = "low") {
    throw new Error("not implemented yet");
  }
  stop() {}
}
