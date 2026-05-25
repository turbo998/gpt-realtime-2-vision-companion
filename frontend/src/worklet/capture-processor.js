// AudioWorklet processor: captures mic at native sample rate, downsamples to
// 24kHz PCM16 mono, posts ArrayBuffer chunks (~40ms) back to the main thread.
class CaptureProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    this.targetRate = (options && options.processorOptions && options.processorOptions.targetRate) || 24000;
    this.inRate = sampleRate; // global in AudioWorkletGlobalScope
    this.ratio = this.inRate / this.targetRate;
    this._buf = [];
    this._chunkSamples = Math.floor(this.targetRate * 0.04); // ~40ms
    this._acc = 0;
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || input.length === 0) return true;
    const ch = input[0];
    if (!ch) return true;
    // Resample by simple decimation/interpolation (linear).
    for (let i = 0; i < ch.length; i += this.ratio) {
      const idx = Math.floor(i);
      const frac = i - idx;
      const a = ch[idx] || 0;
      const b = ch[idx + 1] !== undefined ? ch[idx + 1] : a;
      const s = a + (b - a) * frac;
      this._buf.push(s);
      if (this._buf.length >= this._chunkSamples) this._flush();
    }
    return true;
  }

  _flush() {
    const pcm = new Int16Array(this._buf.length);
    for (let i = 0; i < this._buf.length; i++) {
      let v = Math.max(-1, Math.min(1, this._buf[i]));
      pcm[i] = v < 0 ? v * 0x8000 : v * 0x7fff;
    }
    this._buf = [];
    this.port.postMessage(pcm.buffer, [pcm.buffer]);
  }
}

registerProcessor("capture-processor", CaptureProcessor);
