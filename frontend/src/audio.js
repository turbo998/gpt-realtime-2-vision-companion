// PCM16 mono 24kHz capture (AudioWorklet) + playback (ScriptProcessor-free
// scheduled AudioBuffer queue). Exposes a small event-style API.

const TARGET_RATE = 24000;

export class AudioPipeline {
  constructor() {
    this.ctx = null;
    this.stream = null;
    this.workletNode = null;
    this.source = null;
    this.onPcm = null; // (ArrayBuffer) => void
    this.onLevel = null; // (level: 0..1) => void  (mic VU for interrupt UX)
    this._playHead = 0;
    this._playing = false;
  }

  async start({ onPcm, onLevel } = {}) {
    this.onPcm = onPcm;
    this.onLevel = onLevel;
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
      video: false,
    });
    this.ctx = new (window.AudioContext || window.webkitAudioContext)({
      sampleRate: 48000,
    });
    await this.ctx.audioWorklet.addModule(
      new URL("./worklet/capture-processor.js", import.meta.url),
    );
    this.source = this.ctx.createMediaStreamSource(this.stream);
    this.workletNode = new AudioWorkletNode(this.ctx, "capture-processor", {
      processorOptions: { targetRate: TARGET_RATE },
    });
    this.workletNode.port.onmessage = (e) => {
      const buf = e.data; // ArrayBuffer of Int16
      if (this.onPcm) this.onPcm(buf);
      if (this.onLevel) {
        const i16 = new Int16Array(buf);
        let sum = 0;
        for (let i = 0; i < i16.length; i++) sum += Math.abs(i16[i]);
        const avg = sum / i16.length / 32768;
        this.onLevel(avg);
      }
    };
    this.source.connect(this.workletNode);
    // Worklet must connect to destination to actually pull audio in some browsers.
    const mute = this.ctx.createGain();
    mute.gain.value = 0;
    this.workletNode.connect(mute).connect(this.ctx.destination);
    this._playHead = this.ctx.currentTime;
  }

  // Queue an incoming PCM16 24kHz chunk for low-latency playback.
  enqueuePlayback(pcm16Bytes) {
    if (!this.ctx) return;
    const i16 = new Int16Array(pcm16Bytes.buffer || pcm16Bytes);
    const f32 = new Float32Array(i16.length);
    for (let i = 0; i < i16.length; i++) f32[i] = i16[i] / 32768;
    const audioBuf = this.ctx.createBuffer(1, f32.length, TARGET_RATE);
    audioBuf.getChannelData(0).set(f32);
    const src = this.ctx.createBufferSource();
    src.buffer = audioBuf;
    src.connect(this.ctx.destination);
    const now = this.ctx.currentTime;
    if (this._playHead < now + 0.02) this._playHead = now + 0.02;
    src.start(this._playHead);
    this._playHead += audioBuf.duration;
    this._playing = true;
    src.onended = () => {
      if (this._playHead - this.ctx.currentTime < 0.01) this._playing = false;
    };
  }

  flushPlayback() {
    // Reset playback head — used after a barge-in/interrupt to drop queued audio.
    if (this.ctx) this._playHead = this.ctx.currentTime;
    this._playing = false;
  }

  get isPlaying() {
    return this._playing;
  }

  stop() {
    try {
      if (this.workletNode) this.workletNode.disconnect();
    } catch {}
    try {
      if (this.source) this.source.disconnect();
    } catch {}
    if (this.stream) this.stream.getTracks().forEach((t) => t.stop());
    if (this.ctx) this.ctx.close().catch(() => {});
    this.ctx = null;
    this.stream = null;
    this.workletNode = null;
    this.source = null;
  }
}
