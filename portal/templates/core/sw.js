{% load static %}// Schlanker Service Worker: macht das Portal installierbar und zeigt ohne Netz eine Offline-Seite.
// Inhalte werden bewusst nicht zwischengespeichert (personenbezogene Daten, immer aktueller Stand).
const CACHE = "wtsv-offline-v1";
const OFFLINE_URL = "{% url 'offline' %}";

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll([
    OFFLINE_URL,
    "{% static 'vendor/bootstrap/bootstrap.min.css' %}",
    "{% static 'css/theme.css' %}",
    "{% static 'js/theme-init.js' %}",
    "{% static 'img/logo/logo-schwarz.png' %}",
    "{% static 'img/logo/logo-weiss.png' %}"
  ])));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys().then((keys) =>
    Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)))
  ).then(() => self.clients.claim()));
});

self.addEventListener("fetch", (event) => {
  if (event.request.mode === "navigate") {
    event.respondWith(fetch(event.request).catch(() => caches.match(OFFLINE_URL)));
  }
});
