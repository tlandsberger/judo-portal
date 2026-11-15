// Hinweis „Als App installieren“ auf Handy und Tablet, solange das Portal nicht als App läuft.
// Android/Chrome/Edge: echter Installationsdialog (beforeinstallprompt). iPhone/iPad: Anleitung, da Safari keine
// Schnittstelle bietet. Nach „Später“ 30 Tage Ruhe.
(function () {
  var KEY = "wtsv-install-later";
  var PAUSE_MS = 30 * 24 * 60 * 60 * 1000;
  var element = document.getElementById("install-prompt");
  if (!element || typeof bootstrap === "undefined") return;

  var ua = navigator.userAgent;
  var standalone = window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  var ios = /iPhone|iPad|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  var mobile = ios || /Android|Mobi/i.test(ua);
  if (standalone || !mobile || pausedRecently()) return;

  var offcanvas = bootstrap.Offcanvas.getOrCreateInstance(element);
  var deferred = null;
  var installed = false;

  function pausedRecently() {
    try {
      var until = parseInt(localStorage.getItem(KEY) || "0", 10);
      return until > Date.now();
    } catch (e) { return false; }
  }
  function pause() {
    try { localStorage.setItem(KEY, String(Date.now() + PAUSE_MS)); } catch (e) {}
  }
  function show(variant) {
    element.querySelectorAll("[data-install-variant]").forEach(function (part) {
      part.hidden = part.getAttribute("data-install-variant") !== variant;
    });
    offcanvas.show();
  }

  element.addEventListener("hidden.bs.offcanvas", function () {
    if (!installed) pause();
  });
  element.querySelectorAll("[data-install-later]").forEach(function (button) {
    button.addEventListener("click", function () { offcanvas.hide(); });
  });
  element.querySelector("[data-install-accept]").addEventListener("click", function () {
    if (!deferred) return;
    deferred.prompt();
    deferred.userChoice.then(function (choice) {
      if (choice && choice.outcome === "accepted") installed = true;
      deferred = null;
      offcanvas.hide();
    });
  });

  window.addEventListener("beforeinstallprompt", function (event) {
    event.preventDefault();
    deferred = event;
    show("prompt");
  });
  window.addEventListener("appinstalled", function () {
    installed = true;
    offcanvas.hide();
  });

  // Safari auf iPhone/iPad (andere iOS-Browser können nicht installieren): Anleitung nach kurzer Wartezeit.
  if (ios && /Safari/.test(ua) && !/CriOS|FxiOS|EdgiOS/.test(ua)) {
    window.setTimeout(function () { show("ios"); }, 1500);
  }
})();
