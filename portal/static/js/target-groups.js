// Zielgruppen im Formular der Veranstaltung: Blöcke hinzufügen und Vorlagen als Kopie übernehmen.
// Ohne JavaScript lassen sich bestehende Zielgruppen weiter bearbeiten und entfernen.
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

  const add = () => {
    const index = Number(total.value);
    const html = empty.innerHTML.replaceAll("__prefix__", String(index));
    list.insertAdjacentHTML("beforeend", html);
    total.value = String(index + 1);
    const block = list.lastElementChild;
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
