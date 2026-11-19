// Zielgruppen im Formular der Veranstaltung: Blöcke hinzufügen, entfernen und Vorlagen als Kopie übernehmen.
// „Zielgruppe entfernen“ setzt das versteckte Löschfeld des Formsets und blendet den Block aus. Ohne JavaScript bleibt
// stattdessen das Kästchen.
(() => {
  const section = document.querySelector("[data-target-groups]");
  if (!section) return;
  const prefix = section.dataset.prefix;
  const list = section.querySelector("[data-target-group-list]");
  const empty = section.querySelector("[data-target-group-empty]");
  const total = section.querySelector(`input[name="${prefix}-TOTAL_FORMS"]`);
  const actions = section.querySelector("[data-target-group-actions]");
  const dataElement = document.getElementById("zielgruppen-vorlagen");
  const templates = dataElement ? JSON.parse(dataElement.textContent) : {};

  // Kästchen „Löschen“ gegen den Knopf tauschen
  const prepare = (block) => {
    const box = block.querySelector("[data-target-group-delete]");
    const button = block.querySelector("[data-target-group-remove]");
    if (!box || !button) return;
    box.hidden = true;
    button.hidden = false;
  };

  // Wie beim Hinzufügen gilt das Entfernen erst mit „Speichern“: der Block verschwindet, das Löschfeld ist gesetzt.
  const remove = (block) => {
    block.querySelector("[data-target-group-delete] input[type=checkbox]").checked = true;
    block.hidden = true;
    section.querySelector("[data-target-group-add]")?.focus();
  };

  list.addEventListener("click", (event) => {
    const button = event.target.closest("[data-target-group-remove]");
    if (button) remove(button.closest("[data-target-group]"));
  });
  for (const block of list.querySelectorAll("[data-target-group]")) prepare(block);

  const add = () => {
    const index = Number(total.value);
    const html = empty.innerHTML.replaceAll("__prefix__", String(index));
    list.insertAdjacentHTML("beforeend", html);
    total.value = String(index + 1);
    const block = list.lastElementChild;
    prepare(block);
    return { block, field: (name) => block.querySelectorAll(`[name="${prefix}-${index}-${name}"]`) };
  };

  const fill = ({ field }, values) => {
    for (const [name, value] of Object.entries(values)) {
      const inputs = field(name);
      if (Array.isArray(value)) {
        const wanted = value.map(String);
        for (const input of inputs) input.checked = wanted.includes(input.value);
      } else if (inputs[0]) {
        inputs[0].value = value === null ? "" : String(value);
      }
    }
  };

  section.querySelector("[data-target-group-add]").addEventListener("click", () => {
    add().block.querySelector("input:not([type=hidden])")?.focus();
  });
  const apply = section.querySelector("[data-target-group-apply]");
  if (apply) {
    apply.addEventListener("click", () => {
      const values = templates[section.querySelector("[data-target-group-template]").value];
      if (!values) return;
      const added = add();
      fill(added, values);
      added.block.querySelector("input:not([type=hidden])")?.focus();
    });
  }
  actions.hidden = false;
})();
