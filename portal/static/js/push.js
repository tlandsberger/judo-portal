// Push-Benachrichtigungen ein- und ausschalten („Meine Anmeldung“) und Hinweis auf der Startseite (ADR 0011).
// Elemente mit data-push; ihr Zustand wird über data-push-state gezeigt: off, on, denied, unsupported, error.
(function () {
  var roots = document.querySelectorAll("[data-push]");
  if (!roots.length) return;
  var DISMISS_KEY = "wtsv-push-teaser-dismissed";
  var supported = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
  var known = [];
  try {
    var script = document.getElementById("push-endpoints");
    known = script ? JSON.parse(script.textContent) : [];
  } catch (e) { known = []; }

  function setState(root, state) {
    root.querySelectorAll("[data-push-state]").forEach(function (part) {
      part.hidden = part.getAttribute("data-push-state") !== state;
    });
  }
  function dismissed() {
    try { return localStorage.getItem(DISMISS_KEY) === "1"; } catch (e) { return false; }
  }
  function keyBytes(base64) {
    var padded = (base64 + "===".slice((base64.length + 3) % 4)).replace(/-/g, "+").replace(/_/g, "/");
    var raw = atob(padded);
    var bytes = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
    return bytes;
  }
  function post(url, csrf, body) {
    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      body: JSON.stringify(body),
    }).then(function (response) {
      if (!response.ok) throw new Error("HTTP " + response.status);
      return response;
    });
  }
  function current() {
    return navigator.serviceWorker.ready.then(function (registration) {
      return registration.pushManager.getSubscription();
    });
  }

  function enable(root) {
    Notification.requestPermission().then(function (permission) {
      if (permission !== "granted") {
        setState(root, "denied");
        return null;
      }
      return navigator.serviceWorker.ready
        .then(function (registration) {
          return registration.pushManager.getSubscription().then(function (existing) {
            return existing || registration.pushManager.subscribe({
              userVisibleOnly: true,
              applicationServerKey: keyBytes(root.getAttribute("data-push-key")),
            });
          });
        })
        .then(function (subscription) {
          return post(root.getAttribute("data-push-url"), root.getAttribute("data-csrf"), subscription.toJSON());
        })
        .then(function () { window.location.reload(); });
    }).catch(function () { setState(root, "error"); });
  }

  function disable(root) {
    current().then(function (subscription) {
      if (!subscription) return null;
      return post(root.getAttribute("data-push-unsubscribe-url"), root.getAttribute("data-csrf"), {
        endpoint: subscription.endpoint,
      }).then(function () { return subscription.unsubscribe(); });
    }).then(function () { window.location.reload(); }).catch(function () { setState(root, "error"); });
  }

  roots.forEach(function (root) {
    var teaser = root.hasAttribute("data-push-teaser");
    root.querySelectorAll("[data-push-enable]").forEach(function (button) {
      button.addEventListener("click", function () { enable(root); });
    });
    root.querySelectorAll("[data-push-disable]").forEach(function (button) {
      button.addEventListener("click", function () { disable(root); });
    });
    root.querySelectorAll("[data-push-dismiss]").forEach(function (button) {
      button.addEventListener("click", function () {
        try { localStorage.setItem(DISMISS_KEY, "1"); } catch (e) {}
        root.hidden = true;
      });
    });

    if (!supported) {
      if (!teaser) setState(root, "unsupported");
      return;
    }
    if (teaser && (dismissed() || Notification.permission === "denied")) return;
    current().then(function (subscription) {
      // Nur als eingeschaltet zeigen, wenn der Server das Abo auch kennt (z. B. nicht in der Geräteliste entfernt).
      var on = subscription && known.indexOf(subscription.endpoint) !== -1;
      if (teaser) {
        root.hidden = on;
      } else if (on) {
        setState(root, "on");
      } else {
        setState(root, Notification.permission === "denied" ? "denied" : "off");
      }
    });
  });
})();
