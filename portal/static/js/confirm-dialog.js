// Bestätigung per DaisyUI-Dialog: Ein Formular mit data-confirm-dialog="<id>" öffnet beim Abschicken erst den Dialog.
// Dessen Knopf name="confirmed" schickt das Formular ab; „Abbrechen“ schließt ihn. Ohne JavaScript zeigt der Server
// den Dialog nach dem ersten Abschicken (Attribut open), der Knopf darin bestätigt.
(() => {
  for (const form of document.querySelectorAll("form[data-confirm-dialog]")) {
    const dialog = document.getElementById(form.dataset.confirmDialog);
    if (!dialog || typeof dialog.showModal !== "function") continue;
    form.addEventListener("submit", (event) => {
      if (event.submitter && event.submitter.name === "confirmed") return;
      event.preventDefault();
      dialog.showModal();
    });
    for (const cancel of dialog.querySelectorAll("[data-dialog-cancel]")) {
      cancel.addEventListener("click", (event) => {
        event.preventDefault();
        dialog.close();
      });
    }
  }
})();
