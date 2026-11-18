// Formulare mit data-auto-submit (Filter der Termine, Tag im Trainingstausch) gelten sofort; ohne JavaScript gibt es einen Knopf.
(() => {
  for (const form of document.querySelectorAll("form[data-auto-submit]")) {
    form.addEventListener("change", () => form.requestSubmit());
  }
})();
