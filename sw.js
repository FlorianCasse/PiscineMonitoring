const CACHE = 'piscine-SW_VERSION_PLACEHOLDER';
const STATIC = ['./', './index.html', './manifest.json', './icon.svg'];

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

async function cacheFirst(req) {
  const cached = await caches.match(req);
  if (cached) return cached;
  try {
    const res = await fetch(req);
    if (res.ok) (await caches.open(CACHE)).put(req, res.clone());
    return res;
  } catch (_) {
    return new Response('Offline', { status: 503 });
  }
}

async function networkFirst(req) {
  const cache = await caches.open(CACHE);
  try {
    const res = await fetch(req);
    if (res.ok) cache.put(req, res.clone());
    return res;
  } catch (_) {
    const cached = await cache.match(req);
    return cached || new Response('{}', { status: 503, headers: { 'Content-Type': 'application/json' } });
  }
}
