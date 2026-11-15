// Setzt das Farbschema vor dem ersten Zeichnen: gespeicherte Wahl oder die Geräteeinstellung.
(function () {
  var stored = null;
  try { stored = localStorage.getItem("wtsv-theme"); } catch (e) {}
  var dark = stored ? stored === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.setAttribute("data-theme", dark ? "wtsv-dark" : "wtsv-light");
})();
