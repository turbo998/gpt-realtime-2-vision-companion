// Accessibility state machine: maps UI state -> visual / haptic / audio cues.
const STATE_LABELS = {
  idle: "准备就绪",
  listening: "正在聆听",
  thinking: "思考中",
  speaking: "正在回答",
  error: "出错了",
};

const VIBRATIONS = {
  idle: 0,
  listening: 30,
  thinking: [20, 40, 20],
  speaking: 50,
  error: [80, 60, 80, 60, 80],
};

export function setState(state, message) {
  const btn = document.getElementById("primary-action");
  const status = document.getElementById("status");
  if (btn) {
    btn.dataset.state = state;
    btn.setAttribute("aria-label", STATE_LABELS[state] || state);
    const label = btn.querySelector(".primary-action__label");
    if (label) {
      label.dataset.state = state;
      label.textContent = message || STATE_LABELS[state] || state;
    }
  }
  if (status) status.textContent = message || STATE_LABELS[state] || state;

  if (navigator.vibrate && VIBRATIONS[state] !== undefined) {
    try {
      navigator.vibrate(VIBRATIONS[state]);
    } catch {
      /* noop */
    }
  }
  // TODO: play short distinct cue per state (accessibility todo)
}
