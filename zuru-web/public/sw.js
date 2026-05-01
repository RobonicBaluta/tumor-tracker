// Tumor Tracker — service worker.
// Estrategia:
//   - HTML/navegación: network-first → siempre vemos el deploy nuevo al instante
//   - Assets hasheados (JS/CSS/imágenes): stale-while-revalidate, seguros porque
//     el filename cambia con cada build (no se sirve un asset obsoleto bajo el
//     mismo nombre)
//   - Bumpeamos CACHE_VERSION cuando cambian las reglas para invalidar todo lo
//     anterior en el activate.
const CACHE_VERSION = 'tt-v2'
const CACHE_ASSETS = [
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
  if (event.request.method !== 'GET' || url.origin !== self.location.origin) return
  if (url.pathname.startsWith('/api/') || url.hostname.includes('onrender.com')) return

  const isHtml = event.request.mode === 'navigate' || url.pathname === '/' || url.pathname.endsWith('.html')

  if (isHtml) {
    // Network-first: siempre intenta traer el HTML fresco del deploy.
    // Solo cae al cache si la red falla (ofline).
    event.respondWith(
      fetch(event.request)
        .then((res) => {
          if (res.ok) {
            const clone = res.clone()
            caches.open(CACHE_VERSION).then((cache) => cache.put(event.request, clone))
          }
          return res
        })
        .catch(() => caches.match(event.request).then((c) => c || caches.match('/')))
    )
    return
  }

  // Stale-while-revalidate para assets hasheados.
  event.respondWith(
    caches.match(event.request).then((cached) => {
      const fetchPromise = fetch(event.request)
        .then((res) => {
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
