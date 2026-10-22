/**
 * ResQAI - Progressive Web App Service Worker
 * Caches core application shell, offline safety guidance, and provides offline fallback notice.
 */

const CACHE_NAME = 'resqai-v2.5';
const ASSETS_TO_CACHE = [
  '/',
  '/index.html',
  '/css/main.css',
  '/css/components.css',
  '/css/map.css',
  '/vendor/leaflet.css',
  '/vendor/leaflet.js',
  '/vendor/chart.umd.min.js',
  '/js/app.js',
  '/js/map.js',
  '/js/incidents.js',
  '/js/risk.js',
  '/js/auth.js',
  '/manifest.json'
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS_TO_CACHE).catch(() => {});
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((k) => {
          if (k !== CACHE_NAME) return caches.delete(k);
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  // Let API requests go to network with offline fallback
  if (e.request.url.includes('/api/')) {
    e.respondWith(
      fetch(e.request).catch(() => {
        return new Response(JSON.stringify({
          error: 'Offline mode active. Live data and new submissions require network connectivity.',
          status: 'OFFLINE_FALLBACK'
        }), {
          headers: { 'Content-Type': 'application/json' }
        });
      })
    );
    return;
  }

  // Application shell cache first, network fallback
  e.respondWith(
    caches.match(e.request).then((cached) => {
      return cached || fetch(e.request).catch(() => {
        if (e.request.destination === 'document') {
          return caches.match('/');
        }
      });
    })
  );
});
