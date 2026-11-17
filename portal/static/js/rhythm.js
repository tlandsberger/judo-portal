// Zeitplan-Rhythmus: je nach Auswahl „Alle x Wochen“ oder „Jeden n-ten im Monat“ nur das passende Feld zeigen.
// Ohne JavaScript bleiben beide sichtbar; die Auswahl entscheidet trotzdem, was gespeichert wird.
(() => {
  for (const form of document.querySelectorAll("form")) {
    const radios = form.querySelectorAll("input[data-rhythm]");
    if (!radios.length) continue;
    const fields = form.querySelectorAll("[data-rhythm-for]");
    const update = () => {
      const checked = form.querySelector("input[data-rhythm]:checked");
      for (const field of fields) {
        const group = field.closest(".fieldset") || field;
        group.hidden = !checked || field.dataset.rhythmFor !== checked.value;
      }
    };
    for (const radio of radios) radio.addEventListener("change", update);
    update();
  }
})();
