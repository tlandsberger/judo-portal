// Umschalter Hell/Dunkel, Service Worker und kleine Komfortfunktionen.
(function () {
  var media = window.matchMedia("(prefers-color-scheme: dark)");

  function stored() {
    try { return localStorage.getItem("wtsv-theme"); } catch (e) { return null; }
  }
  function apply(theme) {
    document.documentElement.setAttribute("data-bs-theme", theme);
    document.querySelectorAll("[data-theme-toggle]").forEach(function (button) {
      var dark = theme === "dark";
      button.setAttribute("aria-pressed", String(dark));
      button.setAttribute("aria-label", dark ? "Helles Design einschalten" : "Dunkles Design einschalten");
      button.setAttribute("title", button.getAttribute("aria-label"));
      var icon = button.querySelector(".bi");
      if (icon) icon.className = "bi " + (dark ? "bi-sun" : "bi-moon-stars");
    });
  }

  document.addEventListener("click", function (event) {
    var button = event.target.closest("[data-theme-toggle]");
    if (!button) return;
    var next = document.documentElement.getAttribute("data-bs-theme") === "dark" ? "light" : "dark";
    try { localStorage.setItem("wtsv-theme", next); } catch (e) {}
    apply(next);
  });
  media.addEventListener("change", function (event) {
    if (!stored()) apply(event.matches ? "dark" : "light");
  });
  document.addEventListener("DOMContentLoaded", function () {
    apply(document.documentElement.getAttribute("data-bs-theme") || "light");
  });

  // Kopieren in die Zwischenablage: <button data-copy-target="#feld">
  document.addEventListener("click", function (event) {
    var button = event.target.closest("[data-copy-target]");
    if (!button) return;
    var field = document.querySelector(button.getAttribute("data-copy-target"));
    if (!field) return;
    var status = document.querySelector("[data-copy-status]");
    function done(ok) {
      if (status) status.textContent = ok ? "Link in die Zwischenablage kopiert." : "Kopieren nicht möglich – bitte den Link markieren und kopieren.";
    }
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(field.value).then(function () { done(true); }, function () { done(false); });
    } else {
      field.select();
      try { done(document.execCommand("copy")); } catch (e) { done(false); }
    }
  });

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/sw.js").catch(function () {});
    });
  }
})();
