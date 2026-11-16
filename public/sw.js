// Offline support: app shell cache-first; data network-first with the last copy as fallback,
// so the morning report still opens on a chairlift with no signal.
const SHELL = "shell-v16-quick-wins";
const DATA = "data-v1";
const SHELL_FILES = [
  "/", "/index.html", "/appearance.js", "/report-ui.js", "/app.js", "/app.css", "/themes.css", "/frost.css", "/dark.css",
  "/config.json", "/resorts.json", "/icon.svg", "/icon-180.png", "/icon-192.png", "/icon-512.png", "/manifest.webmanifest",
  "/brand/fonts/outfit.woff2", "/brand/fonts/plex-sans.woff2", "/brand/fonts/plex-mono.woff2", "/brand/frosted-logo.webp",
  "/brand/app-icon-dark-180.png", "/brand/app-icon-dark-192.png", "/brand/app-icon-dark-512.png",
];

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
    e.respondWith(networkFirst(e.request, DATA, () => caches.match(e.request, { ignoreSearch: true })));
    return;
  }
  // App shell: network first so a new deploy shows on the next open; cache only when offline.
  e.respondWith(networkFirst(e.request, SHELL, () => caches.match(e.request, { ignoreSearch: true }).then((hit) => hit || caches.match("/index.html"))));
});

// Network first, but never wait forever. When iOS launches the Home Screen app from a
// notification tap the first requests can stall with no error, which left Today stuck on its
// loading cards. After a few seconds the saved copy answers, and the network copy still
// refreshes the cache when it lands.
const WAIT_MS = 3500;
function networkFirst(req, cacheName, fallback) {
  const net = fetch(req).then((res) => {
    if (res.ok) { const copy = res.clone(); caches.open(cacheName).then((c) => c.put(req, copy)); }
    return res;
  });
  return new Promise((resolve, reject) => {
    let done = false;
    const finish = (res) => { if (!done && res) { done = true; resolve(res); } };
    const useCache = () => fallback().then((hit) => { if (hit) finish(hit); else if (!done) net.then(finish, () => { if (!done) reject(new TypeError("offline")); }); });
    const timer = setTimeout(useCache, WAIT_MS);
    net.then((res) => { clearTimeout(timer); finish(res); }, () => { clearTimeout(timer); useCache(); });
  });
}

// App notifications: the morning report (at most one a day; powder alerts ride along).
self.addEventListener("push", (e) => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (err) { d = { title: "Snow Desk", body: e.data ? e.data.text() : "" }; }
  e.waitUntil(self.registration.showNotification(d.title || "Snow Desk", {
    body: d.body || "", tag: d.tag || "chair-0", icon: "/icon-512.png", badge: "/icon-180.png",
    image: d.image, data: { url: d.url || "/" },
  }));
});
self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || "/";
  // An open app window is told which report to show and brought forward; it reloads its data
  // itself. (Navigating a suspended iOS window from here often does nothing, so the page that
  // was frozen mid-load stayed blank.) With no window open, the app opens at the link.
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((wins) => {
    const w = wins.find((c) => "focus" in c);
    if (w) { w.postMessage({ type: "open-report", url }); return w.focus().catch(() => self.clients.openWindow(url)); }
    return self.clients.openWindow(url);
  }));
});
