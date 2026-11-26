// Chat mit Uke ohne Neuladen: Frage sofort anzeigen, „denkt nach“ einblenden, Antwort als HTML-Schnipsel anhängen.
// Ohne JavaScript schickt das Formular normal ab und die Seite lädt neu.
(function () {
  var form = document.querySelector("form[data-uke]");
  if (!form) return;
  var log = document.getElementById("verlauf");
  var errors = document.getElementById("uke-fehler");
  var field = form.querySelector("textarea");
  var busy = false;

  function append(templateId, text) {
    var node = document.getElementById(templateId).content.firstElementChild.cloneNode(true);
    var target = node.querySelector("[data-text]");
    if (target) target.textContent = text;
    log.appendChild(node);
    node.scrollIntoView({ block: "end", behavior: "smooth" });
    return node;
  }

  // Enter schickt ab, Umschalt+Enter macht eine neue Zeile
  field.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var text = field.value.trim();
    if (!text || busy) return;
    busy = true;
    errors.replaceChildren();
    var data = new FormData(form);
    append("uke-frage", text);
    var thinking = append("uke-denkt");
    field.value = "";
    fetch(form.action, { method: "POST", body: data, headers: { "X-Uke": "1" }, credentials: "same-origin" })
      .then(function (response) {
        return response.text().then(function (html) { return { ok: response.ok, html: html }; });
      })
      .then(function (result) {
        thinking.remove();
        var holder = document.createElement("div");
        holder.innerHTML = result.html;
        if (result.ok) {
          var reply = holder.firstElementChild;
          log.appendChild(reply);
          reply.scrollIntoView({ block: "end", behavior: "smooth" });
        } else {
          errors.replaceChildren.apply(errors, Array.from(holder.childNodes));
        }
      })
      .catch(function () {
        thinking.remove();
        errors.textContent = "Keine Verbindung. Versuch es bitte noch einmal.";
      })
      .finally(function () {
        busy = false;
        field.focus();
      });
  });
})();
