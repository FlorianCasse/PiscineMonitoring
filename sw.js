const CACHE = 'piscine-SW_VERSION_PLACEHOLDER';
const STATIC = ['./', './index.html', './manifest.json', './icon.svg'];

// Origins whose responses are safe to serve/cache from this scope.
// Keep in sync with the connect-src directive in index.html's CSP.
const ALLOWED_ORIGINS = new Set([
  self.location.origin,
  'https://api.open-meteo.com',
]);

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE)
      .then(c => c.addAll(STATIC))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  // External requests (e.g. Open-Meteo API) bypass the cache entirely
  if (url.hostname !== self.location.hostname) {
    e.respondWith(fetch(e.request));
    return;
  }
  const isData = url.pathname.endsWith('status.json')
    || url.pathname.endsWith('history.json')
    || url.pathname.endsWith('daily_summary.json');
  e.respondWith(isData ? networkFirst(e.request) : cacheFirst(e.request));
});

// Only cache responses that are same-origin (or explicitly allow-listed),
// not redirected, not opaque, and returned a 2xx status. This defends
// against cross-origin cache poisoning on hostile networks.
function isSafeToCache(res) {
  if (!res || !res.ok) return false;
  if (res.redirected) return false;
  if (res.type === 'opaque' || res.type === 'opaqueredirect') return false;
  try {
    const origin = new URL(res.url).origin;
    if (!ALLOWED_ORIGINS.has(origin)) return false;
  } catch (_) {
    return false;
  }
  return true;
}

async function cacheFirst(req) {
  const cached = await caches.match(req);
  if (cached) return cached;
  try {
    const res = await fetch(req);
    if (isSafeToCache(res)) (await caches.open(CACHE)).put(req, res.clone());
    return res;
  } catch (_) {
    return new Response('Offline', { status: 503 });
  }
}

async function networkFirst(req) {
  const cache = await caches.open(CACHE);
  try {
    const res = await fetch(req);
    if (isSafeToCache(res)) cache.put(req, res.clone());
    return res;
  } catch (_) {
    const cached = await cache.match(req);
    return cached || new Response('{}', { status: 503, headers: { 'Content-Type': 'application/json' } });
  }
}
