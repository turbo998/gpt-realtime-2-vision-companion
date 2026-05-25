// Minimal service worker — only serves to make the app installable.
// We intentionally do NOT cache app shell so realtime API/WSS always hits network fresh.
self.addEventListener("install", (e) => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", () => {});
