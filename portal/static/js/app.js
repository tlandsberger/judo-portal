// Umschalter Hell/Dunkel, Service Worker und kleine Komfortfunktionen.
(function () {
  var media = window.matchMedia("(prefers-color-scheme: dark)");

  function stored() {
    try { return localStorage.getItem("wtsv-theme"); } catch (e) { return null; }
  }
  function current() {
    return document.documentElement.getAttribute("data-theme") === "wtsv-dark" ? "dark" : "light";
  }
  function apply(theme) {
    var dark = theme === "dark";
    document.documentElement.setAttribute("data-theme", dark ? "wtsv-dark" : "wtsv-light");
    document.querySelectorAll("[data-theme-toggle]").forEach(function (button) {
      button.setAttribute("aria-pressed", String(dark));
      button.setAttribute("aria-label", dark ? "Helles Design einschalten" : "Dunkles Design einschalten");
      button.setAttribute("title", button.getAttribute("aria-label"));
      var icon = button.querySelector(".bi");
      if (icon) icon.className = "bi text-lg " + (dark ? "bi-sun" : "bi-moon-stars");
      var label = button.querySelector("[data-theme-label]");
      if (label) label.textContent = dark ? "Helles Design" : "Dunkles Design";
    });
  }

  document.addEventListener("click", function (event) {
    var button = event.target.closest("[data-theme-toggle]");
    if (!button) return;
    var next = current() === "dark" ? "light" : "dark";
    try { localStorage.setItem("wtsv-theme", next); } catch (e) {}
    apply(next);
  });
  media.addEventListener("change", function (event) {
    if (!stored()) apply(event.matches ? "dark" : "light");
  });
  document.addEventListener("DOMContentLoaded", function () {
    apply(current());
  });

  // Seitenleiste am Handy: Menü-Button auch per Tastatur bedienbar, Escape schließt sie wieder.
  document.addEventListener("keydown", function (event) {
    var drawer = document.getElementById("navigation");
    if (!drawer) return;
    if ((event.key === "Enter" || event.key === " ") && event.target.closest("[data-drawer-open]")) {
      event.preventDefault();
      drawer.checked = true;
      var first = document.querySelector(".drawer-side a");
      if (first) first.focus();
    } else if (event.key === "Escape" && drawer.checked) {
      drawer.checked = false;
      var opener = document.querySelector("[data-drawer-open]");
      if (opener) opener.focus();
    }
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

  // Am Handy ist die Hauptaktions-Leiste fixiert und kann zweizeilig werden: Platz darunter so hoch wie die Leiste,
  // damit Inhalt und Footer nicht verdeckt werden (Ersatzwert ohne JavaScript in app.css).
  var bar = document.querySelector(".action-bar");
  if (bar && "ResizeObserver" in window) {
    new ResizeObserver(function () {
      var fixed = getComputedStyle(bar).position === "fixed";
      document.documentElement.style.setProperty("--action-bar-space", fixed ? bar.offsetHeight + "px" : "0px");
    }).observe(bar);
  }

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/sw.js").catch(function () {});
    });
  }
})();
