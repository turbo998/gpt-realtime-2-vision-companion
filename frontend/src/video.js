// Camera capture + low/high-res JPEG extraction via OffscreenCanvas.
export class VideoPipeline {
  constructor(videoEl) {
    this.videoEl = videoEl;
    this.stream = null;
    this._lowCanvas = null;
    this._highCanvas = null;
  }

  async start() {
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: {
        facingMode: { ideal: "environment" },
        width: { ideal: 1280 },
        height: { ideal: 720 },
      },
    });
    if (this.videoEl) {
      this.videoEl.srcObject = this.stream;
      await this.videoEl.play().catch(() => {});
    }
  }

  _ensureCanvas(quality) {
    const dims =
      quality === "high" ? { w: 1280, h: 960 } : { w: 640, h: 480 };
    const key = quality === "high" ? "_highCanvas" : "_lowCanvas";
    if (!this[key] || this[key].width !== dims.w) {
      this[key] = new OffscreenCanvas(dims.w, dims.h);
    }
    return this[key];
  }

  async grabFrame(quality = "low") {
    if (!this.videoEl || this.videoEl.readyState < 2) return null;
    const canvas = this._ensureCanvas(quality);
    const ctx = canvas.getContext("2d");
    const vw = this.videoEl.videoWidth || canvas.width;
    const vh = this.videoEl.videoHeight || canvas.height;
    // Cover-fit
    const scale = Math.max(canvas.width / vw, canvas.height / vh);
    const dw = vw * scale;
    const dh = vh * scale;
    ctx.drawImage(this.videoEl, (canvas.width - dw) / 2, (canvas.height - dh) / 2, dw, dh);
    const blob = await canvas.convertToBlob({
      type: "image/jpeg",
      quality: quality === "high" ? 0.85 : 0.7,
    });
    return await blob.arrayBuffer();
  }

  stop() {
    if (this.stream) this.stream.getTracks().forEach((t) => t.stop());
    this.stream = null;
  }
}
