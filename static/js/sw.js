/* RegulaVasc — Service Worker */

const CACHE_NAME = "regulavasc-cache-v1";
const STATIC_ASSETS = [
  "/static/manifest.json",
  "/static/css/app.css",
  "/static/icons/icon.svg",
  "/static/icons/icon-72x72.png",
  "/static/icons/icon-96x96.png",
  "/static/icons/icon-128x128.png",
  "/static/icons/icon-144x144.png",
  "/static/icons/icon-152x152.png",
  "/static/icons/icon-192x192.png",
  "/static/icons/icon-384x384.png",
  "/static/icons/icon-512x512.png",
  "/static/icons/maskable_icon_x192.png",
  "/static/icons/maskable_icon_x512.png",
  "/static/js/pdf-viewer.js",
  "/static/js/work_lock.js",
  "/static/js/decision.js",
  "/static/js/dashboard_search.js",
  "/static/js/password-toggle.js",
  "/static/js/upload.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((names) => {
      return Promise.all(
        names
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      );
    })
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;

  const url = new URL(event.request.url);

  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          return caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, response.clone());
            return response;
          });
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request).catch(() => caches.match("/"))
    );
    return;
  }
});
