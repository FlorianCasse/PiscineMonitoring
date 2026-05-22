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

const DATA_CACHE_MAX_AGE_MS = 24 * 60 * 60 * 1000;

async function networkFirst(req) {
  const cache = await caches.open(CACHE);
  try {
    const res = await fetch(req);
    if (res.ok) {
      const cloned = res.clone();
      const headers = new Headers(cloned.headers);
      headers.set('x-cached-at', String(Date.now()));
      const body = await cloned.blob();
      cache.put(req, new Response(body, { status: cloned.status, statusText: cloned.statusText, headers }));
    }
    return res;
  } catch (_) {
    const cached = await cache.match(req);
    if (cached) {
      const cachedAt = parseInt(cached.headers.get('x-cached-at') || '0', 10);
      if (cachedAt && Date.now() - cachedAt > DATA_CACHE_MAX_AGE_MS) {
        return new Response(JSON.stringify({ entries: [] }), {
          status: 503,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      return cached;
    }
    return new Response(JSON.stringify({ entries: [] }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
