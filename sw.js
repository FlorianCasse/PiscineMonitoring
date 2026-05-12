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
  // Only handle GET — never cache POST/PUT/DELETE
  if (e.request.method !== 'GET') return;

  const url = new URL(e.request.url);

  // Only handle http(s); ignore chrome-extension://, data:, etc.
  if (url.protocol !== 'https:' && url.protocol !== 'http:') return;

  // External requests (e.g. Open-Meteo API) bypass the cache entirely
  if (url.origin !== self.location.origin) {
    e.respondWith(fetch(e.request));
    return;
  }

  const isData = url.pathname.endsWith('status.json')
    || url.pathname.endsWith('history.json')
    || url.pathname.endsWith('daily_summary.json');
  e.respondWith(isData ? networkFirst(e.request) : cacheFirst(e.request));
});

// Only same-origin, non-redirected, 2xx responses may be cached.
// Opaque / opaqueredirect / cors / error responses are never written.
function isCacheable(res) {
  return res && res.ok && res.type === 'basic' && !res.redirected;
}

async function cacheFirst(req) {
  const cached = await caches.match(req);
  if (cached) return cached;
  try {
    const res = await fetch(req);
    if (isCacheable(res)) (await caches.open(CACHE)).put(req, res.clone());
    return res;
  } catch (_) {
    return new Response('Offline', { status: 503 });
  }
}

async function networkFirst(req) {
  const cache = await caches.open(CACHE);
  try {
    const res = await fetch(req);
    if (isCacheable(res)) cache.put(req, res.clone());
    return res;
  } catch (_) {
    const cached = await cache.match(req);
    return cached || new Response('{}', { status: 503, headers: { 'Content-Type': 'application/json' } });
  }
}
