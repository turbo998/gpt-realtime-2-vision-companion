// Lightweight wake-word activation. Implemented in `accessibility` todo.
// Likely options:
//  - on-device energy + simple keyword match (cheap, low accuracy)
//  - Porcupine Web SDK (license required for commercial use)
export class WakeWord {
  async start() {
    throw new Error("not implemented yet");
  }
  stop() {}
}
