// Minimal service worker for PWA install criteria.
// Do NOT cache audio/video streams; we want freshest backend.
const CACHE = "vision-companion-v0.1.0";
const ASSETS = [
  "./",
  "./index.html",
  "./styles/main.css",
  "./manifest.webmanifest",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))),
    ),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  // never intercept ws/api calls
  if (url.pathname.startsWith("/ws") || url.pathname.startsWith("/api")) return;
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request)),
  );
});
