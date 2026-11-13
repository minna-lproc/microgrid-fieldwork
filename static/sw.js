const CACHE = 'gridfield-shell-revised-v4';
const ASSETS = ['/', '/static/style.css', '/static/app.js', '/static/survey.json', '/static/icon.svg', '/static/icon-192.png', '/static/icon-512.png', '/static/manifest.webmanifest'];
self.addEventListener('install', e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)).then(() => self.skipWaiting())); });
self.addEventListener('activate', e => { e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener('fetch', e => {
    const u = new URL(e.request.url); if (e.request.method !== 'GET' || u.origin !== location.origin || u.pathname.startsWith('/api/')) return;
    if (e.request.mode === 'navigate') { e.respondWith(fetch(e.request).catch(() => caches.match('/'))); return; }
    if (ASSETS.includes(u.pathname)) e.respondWith(caches.match(e.request).then(c => c || fetch(e.request)));
});
self.addEventListener('sync', e => { if (e.tag === 'gridfield-sync') e.waitUntil(self.clients.matchAll({ type: 'window' }).then(cs => cs.forEach(c => c.postMessage({ type: 'sync' })))); });
