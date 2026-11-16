// „Nicht dabei?“: die Felder für die Vertretung nur zeigen, wenn „Ich wurde vertreten“ gewählt ist.
// Ohne JavaScript bleiben sie sichtbar; die Auswahl entscheidet trotzdem, was gespeichert wird.
(() => {
  const form = document.querySelector("[data-absent-form]");
  if (!form) return;
  const section = form.querySelector("[data-absent-substitute]");
  const update = () => {
    const checked = form.querySelector('input[name="what"]:checked');
    section.hidden = !checked || checked.value !== "hand_over";
  };
  for (const radio of form.querySelectorAll('input[name="what"]')) radio.addEventListener("change", update);
  update();
})();
