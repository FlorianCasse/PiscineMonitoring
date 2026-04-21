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

// Only handle same-origin GET requests. Known static assets use cache-first;
// known data files use network-first. Anything else is passed through untouched
// (no opportunistic caching of arbitrary URLs — avoids cache poisoning & scope creep).
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  const url = new URL(e.request.url);
  // External requests (e.g. Open-Meteo API) bypass the cache entirely.
  if (url.origin !== self.location.origin) return;

  const path = url.pathname.replace(/^.*\//, './');
  const isStatic = STATIC.includes(path) || path === './';
  const isData = url.pathname.endsWith('status.json')
    || url.pathname.endsWith('history.json')
    || url.pathname.endsWith('daily_summary.json');

  if (isData) {
    e.respondWith(networkFirst(e.request));
  } else if (isStatic || url.pathname.endsWith('.html') || url.pathname.endsWith('/sw.js')) {
    e.respondWith(cacheFirst(e.request));
  }
  // else: let the request pass through to the network untouched.
});

async function cacheFirst(req) {
  const cached = await caches.match(req);
  if (cached) return cached;
  try {
    const res = await fetch(req);
    // Only cache successful, basic (same-origin) responses
    if (res.ok && res.type === 'basic') {
      (await caches.open(CACHE)).put(req, res.clone());
    }
    return res;
  } catch (_) {
    return new Response('Offline', { status: 503 });
  }
}

async function networkFirst(req) {
  const cache = await caches.open(CACHE);
  try {
    const res = await fetch(req);
    if (res.ok && res.type === 'basic') cache.put(req, res.clone());
    return res;
  } catch (_) {
    const cached = await cache.match(req);
    return cached || new Response('{}', { status: 503, headers: { 'Content-Type': 'application/json' } });
  }
}
