// Chat mit Uke (ADR 0028) auf der Seite /uke/ und im Fenster, das der Knopf unten rechts auf jeder Seite öffnet.
// Ohne JavaScript schickt das Formular normal ab und der Knopf führt zur Seite /uke/.
(function () {
  var OPEN_KEY = "uke-offen";
  var wide = window.matchMedia("(min-width: 64rem)");

  function scrollDown(log) {
    log.scrollTop = log.scrollHeight;
  }

  function append(chat, selector, text) {
    var node = chat.querySelector(selector).content.firstElementChild.cloneNode(true);
    var target = node.querySelector("[data-text]");
    if (target) target.textContent = text;
    var log = chat.querySelector("[data-uke-log]");
    log.appendChild(node);
    scrollDown(log);
    return node;
  }

  // Frage abschicken: sofort anzeigen, „denkt nach“, Antwort als HTML-Schnipsel anhängen
  document.addEventListener("submit", function (event) {
    var form = event.target.closest("form[data-uke]");
    if (!form) return;
    event.preventDefault();
    var chat = form.closest("[data-uke-chat]");
    var field = form.querySelector("textarea");
    var errors = chat.querySelector("[data-uke-errors]");
    var text = field.value.trim();
    if (!text || form.dataset.busy) return;
    form.dataset.busy = "1";
    errors.replaceChildren();
    var data = new FormData(form);
    append(chat, "[data-uke-question]", text);
    var thinking = append(chat, "[data-uke-thinking]");
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
          var log = chat.querySelector("[data-uke-log]");
          log.appendChild(holder.firstElementChild);
          scrollDown(log);
        } else {
          errors.replaceChildren.apply(errors, Array.from(holder.childNodes));
        }
      })
      .catch(function () {
        thinking.remove();
        errors.textContent = "Keine Verbindung. Versuch es bitte noch einmal.";
      })
      .finally(function () {
        delete form.dataset.busy;
        field.focus();
      });
  });

  // Enter schickt ab, Umschalt+Enter macht eine neue Zeile
  document.addEventListener("keydown", function (event) {
    var field = event.target.closest && event.target.closest("[data-uke-chat] textarea");
    if (field && event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      field.form.requestSubmit();
    }
  });

  // Seite /uke/: ans Ende des Gesprächs scrollen
  document.querySelectorAll("[data-uke-chat] [data-uke-log]").forEach(scrollDown);

  // Fenster auf allen Seiten: nicht-modal (show statt showModal), damit die Seite daneben bedienbar bleibt
  var panel = document.querySelector("[data-uke-panel]");
  var opener = document.querySelector("[data-uke-open]");
  if (!panel || !opener) return;
  var body = panel.querySelector("[data-uke-body]");
  var loaded = false;
  opener.setAttribute("role", "button");
  opener.setAttribute("aria-controls", panel.id);
  opener.setAttribute("aria-expanded", "false");

  function load() {
    return fetch(panel.dataset.src, { credentials: "same-origin" })
      .then(function (response) {
        if (!response.ok) throw new Error(response.status);
        return response.text();
      })
      .then(function (html) {
        body.innerHTML = html;
        loaded = true;
        scrollDown(body.querySelector("[data-uke-log]"));
      });
  }

  function remember(open) {
    try {
      if (open) sessionStorage.setItem(OPEN_KEY, "1");
      else sessionStorage.removeItem(OPEN_KEY);
    } catch (e) {}
  }

  function focusField() {
    var field = body.querySelector("textarea");
    if (field) field.focus();
  }

  function open(focus) {
    panel.show();
    opener.setAttribute("aria-expanded", "true");
    remember(true);
    var ready = loaded ? Promise.resolve() : load();
    ready.then(function () { if (focus) focusField(); }, function () {
      window.location.href = opener.href; // Fenster klappt nicht: dann eben die Seite
    });
  }

  function close() {
    panel.close();
    opener.setAttribute("aria-expanded", "false");
    remember(false);
    opener.focus();
  }

  opener.addEventListener("click", function (event) {
    event.preventDefault();
    if (panel.open) close();
    else open(true);
  });
  panel.querySelector("[data-uke-close]").addEventListener("click", close);
  panel.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
    }
  });
  panel.querySelector("[data-uke-new]").addEventListener("click", function () {
    var token = body.querySelector("input[name=csrfmiddlewaretoken]");
    if (!token) return;
    var data = new FormData();
    data.append("csrfmiddlewaretoken", token.value);
    fetch(panel.dataset.new, { method: "POST", body: data, headers: { "X-Uke": "1" }, credentials: "same-origin" })
      .then(load)
      .then(focusField);
  });

  // Am Desktop bleibt das Fenster beim Seitenwechsel offen (gleiches Gespräch); am Handy würde es die neue Seite verdecken
  var wasOpen = false;
  try { wasOpen = sessionStorage.getItem(OPEN_KEY) === "1"; } catch (e) {}
  if (wasOpen && wide.matches) open(false);
  else if (wasOpen) remember(false);
})();
