// Termine: Filter-Knöpfe gelten sofort. Ohne JavaScript gibt es den Knopf „Anwenden“.
(() => {
  for (const form of document.querySelectorAll("form[data-auto-submit]")) {
    form.addEventListener("change", () => form.requestSubmit());
  }
})();
