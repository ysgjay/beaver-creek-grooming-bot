// Offline support: app shell cache-first; data network-first with the last copy as fallback,
// so the morning report still opens on a chairlift with no signal.
const SHELL = "shell-v1";
const DATA = "data-v1";
const SHELL_FILES = ["/", "/index.html", "/app.js", "/app.css", "/themes.css", "/config.json", "/icon.svg", "/manifest.webmanifest"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(SHELL).then((c) => c.addAll(SHELL_FILES)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => ![SHELL, DATA].includes(k)).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  if (url.pathname.startsWith("/api/")) return;
  if (url.pathname.startsWith("/data/") || url.pathname.startsWith("/maps/") || url.pathname.startsWith("/cams/")) {
    e.respondWith(fetch(e.request).then((res) => {
      if (res.ok) { const copy = res.clone(); caches.open(DATA).then((c) => c.put(e.request, copy)); }
      return res;
    }).catch(() => caches.match(e.request, { ignoreSearch: true })));
    return;
  }
  e.respondWith(caches.match(e.request, { ignoreSearch: true }).then((hit) => {
    const net = fetch(e.request).then((res) => { if (res.ok) { const copy = res.clone(); caches.open(SHELL).then((c) => c.put(e.request, copy)); } return res; });
    return hit || net;
  }));
});
