// Tumor Tracker — service worker básico.
// Cachea assets estáticos, fallback offline a la SPA.
const CACHE_VERSION = 'tt-v1'
const CACHE_ASSETS = [
  '/',
  '/manifest.json',
]

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => cache.addAll(CACHE_ASSETS))
  )
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k)))
    )
  )
  self.clients.claim()
})

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url)
  // Solo cachea peticiones GET de mismo origen
  if (event.request.method !== 'GET' || url.origin !== self.location.origin) return
  // Bypass para rutas de la API
  if (url.pathname.startsWith('/api/') || url.hostname.includes('onrender.com')) return

  event.respondWith(
    caches.match(event.request).then((cached) => {
      const fetchPromise = fetch(event.request)
        .then((res) => {
          // Cachear assets estáticos (JS, CSS, imágenes, fuentes)
          if (res.ok && /\.(js|css|woff2?|svg|png|jpg|webp|webm|ico)$/i.test(url.pathname)) {
            const clone = res.clone()
            caches.open(CACHE_VERSION).then((cache) => cache.put(event.request, clone))
          }
          return res
        })
        .catch(() => cached || caches.match('/'))
      return cached || fetchPromise
    })
  )
})
