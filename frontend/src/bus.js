// Tiny pub/sub for app state.
const subs = new Map();
export function on(evt, cb) {
  if (!subs.has(evt)) subs.set(evt, new Set());
  subs.get(evt).add(cb);
  return () => subs.get(evt).delete(cb);
}
export function emit(evt, payload) {
  if (!subs.has(evt)) return;
  for (const cb of subs.get(evt)) {
    try {
      cb(payload);
    } catch (e) {
      console.error(e);
    }
  }
}
