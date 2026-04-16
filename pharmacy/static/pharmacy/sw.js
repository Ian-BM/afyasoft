/* Afya Soft — offline shell cache (GET only; API always live when reachable) */
const CACHE = "afyasoft-shell-v7";
const PRECACHE = [
  "/static/pharmacy/css/app.css",
  "/static/pharmacy/js/offline.js",
  "/static/pharmacy/js/sync.js",
  "/static/pharmacy/js/app-shell.js",
  "/static/pharmacy/js/pos.js",
  "/static/pharmacy/js/inventory.js",
  "/static/pharmacy/manifest.webmanifest",
  "/static/pharmacy/img/afyasoft-logo.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) =>
        Promise.all(PRECACHE.map((url) => cache.add(url).catch(() => null)))
      )
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  if (url.pathname.startsWith("/admin")) return;
  if (url.pathname.startsWith("/api/")) return;

  event.respondWith(
    fetch(req)
      .then((res) => {
        if (res.ok && req.mode === "navigate") {
          const copy = res.clone();
          caches.open(CACHE).then((cache) => cache.put(req, copy));
        }
        return res;
      })
      .catch(() =>
        caches.match(req).then((hit) => {
          if (hit) return hit;
          if (req.mode === "navigate") {
            return caches.match("/sales/").then((r) => r || caches.match("/"));
          }
          return Promise.reject(new Error("offline"));
        })
      )
  );
});
