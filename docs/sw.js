// Minimal service worker — makes this an installable PWA (clean home-screen
// icon, no browser badge) and serves the shell offline. Network-first so an
// online visit is always fresh; the live GitHub/Aladhan APIs are never cached.
// Bump the version whenever a shell file is REMOVED — the activate handler only
// deletes other-named caches, so stale entries inside the current one live forever.
const CACHE = 'noterpiper-v2';

self.addEventListener('install', () => self.skipWaiting());

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches
      .keys()
      .then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET') return;
  const url = e.request.url;
  if (url.includes('api.github.com') || url.includes('aladhan.com')) return; // always live
  e.respondWith(
    fetch(e.request)
      .then((res) => {
        if (res.ok) {
          // only cache good responses — a cached 404 would outlive the outage
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(e.request, copy));
        }
        return res;
      })
      .catch(() => caches.match(e.request)),
  );
});
