// „Veranstaltung anlegen“: je nach Auswahl unter „Termine“ nur die passenden Felder zeigen.
// Ohne JavaScript bleiben alle sichtbar; die Auswahl entscheidet trotzdem, was gespeichert wird.
(() => {
  const form = document.querySelector("[data-event-form]");
  if (!form) return;
  const radios = form.querySelectorAll('input[name="dates"]');
  const sections = form.querySelectorAll("[data-dates-for]");
  const update = () => {
    const checked = form.querySelector('input[name="dates"]:checked');
    const mode = checked ? checked.value : "once";
    for (const section of sections) {
      section.hidden = !section.dataset.datesFor.split(" ").includes(mode);
    }
  };
  for (const radio of radios) radio.addEventListener("change", update);
  update();
})();
