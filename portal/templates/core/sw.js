{% load static %}// Schlanker Service Worker: macht das Portal installierbar, zeigt ohne Netz eine Offline-Seite und
// empfängt Push-Nachrichten (ADR 0011).
// Inhalte werden bewusst nicht zwischengespeichert (personenbezogene Daten, immer aktueller Stand).
const CACHE = "wtsv-offline-{{ portal_version }}";
const OFFLINE_URL = "{% url 'offline' %}";
const ACTION_URL = "{% url 'push_action' %}";
const ICON = "{% static 'img/pwa/icon-192.png' %}";
// Symbol in der Statusleiste (Android): nur die Form zählt, Android färbt selbst ein
const BADGE = "{% static 'img/pwa/badge-96.png' %}";

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll([
    OFFLINE_URL,
    "{% static 'vendor/app.css' %}",
    "{% static 'vendor/bootstrap-icons/bootstrap-icons.min.css' %}",
    "{% static 'js/theme-init.js' %}",
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

// Push: Titel, Text, Ziel-URL und optionale Knöpfe (actions) mit signiertem Token kommen vom Server.
self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (error) {
    data = { body: event.data ? event.data.text() : "" };
  }
  const actions = data.actions || [];
  event.waitUntil(self.registration.showNotification(data.title || "Wedeler TSV Judo", {
    body: data.body || "",
    icon: ICON,
    badge: BADGE,
    tag: data.tag,
    data: { url: data.url || "/", actions },
    actions: actions.map((action) => ({ action: action.action, title: action.title })),
  }));
});

function openPage(url) {
  const target = new URL(url || "/", self.location.origin);
  return self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
    for (const client of windows) {
      if (new URL(client.url).pathname === target.pathname && "focus" in client) return client.focus();
    }
    return self.clients.openWindow(target.href);
  });
}

self.addEventListener("notificationclick", (event) => {
  const notification = event.notification;
  const data = notification.data || {};
  notification.close();
  const action = (data.actions || []).find((item) => item.action === event.action);
  if (!action) {
    event.waitUntil(openPage(data.url));
    return;
  }
  // Knopf: Aktion direkt ausführen und das Ergebnis als kurze Nachricht zeigen; klappt es nicht, Seite öffnen.
  event.waitUntil(
    fetch(ACTION_URL, { method: "POST", body: new URLSearchParams({ token: action.token }) })
      .then((response) => response.json())
      .then((result) => {
        const shown = self.registration.showNotification("Wedeler TSV Judo", {
          body: result.message,
          icon: ICON,
          badge: BADGE,
          tag: (notification.tag || "aktion") + "-ergebnis",
        });
        return result.ok ? shown : shown.then(() => openPage(result.url || data.url));
      })
      .catch(() => openPage(data.url)),
  );
});
