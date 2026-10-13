/* YEA Parent Portal service worker.
   Plan B: a later Capacitor shell can wrap the same /portal/ URLs.
   Keep Stripe Checkout in the system browser, not an in-app webview. */
const CACHE_NAME = "yea-parent-portal-v1";

self.addEventListener("install", function (event) {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then(function (cache) {
      return cache.addAll([
        "/static/images/pwa/yea-parent-192.png",
        "/static/images/pwa/yea-parent-512.png",
      ]).catch(function () {
        return undefined;
      });
    })
  );
});

self.addEventListener("activate", function (event) {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", function (event) {
  var request = event.request;
  if (request.method !== "GET") return;
  var url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  event.respondWith(
    fetch(request).catch(function () {
      return caches.match(request);
    })
  );
});
