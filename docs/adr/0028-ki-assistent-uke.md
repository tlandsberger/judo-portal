# 0028 – KI-Assistent „Uke“: lokales Sprachmodell mit Werkzeugen und Benutzerrechten

- Status: angenommen
- Datum: 2026-11-26

## Kontext

Viele Fragen an das Portal sind kurz: „Welche Trainings sind diese Woche?“, „Ist Max am Freitag angemeldet?“, „Wie
richte ich einen Passkey ein?“. Dafür muss man heute die passende Seite kennen und filtern. Ein Assistent, mit dem
man schreibt (später auch spricht), macht das einfacher. Später soll er auch Aufgaben erledigen, etwa „Melde Max zum
Training heute Abend an“ oder „Ich kann heute nicht, Clara vertritt mich“.

Vorgaben:
- **Lokal:** Fragen und Daten verlassen den Server des Vereins nicht.
- **Benutzerrechte:** Der Assistent darf nur, was der Benutzer selbst darf.
- **Bestätigung:** Alles, was Daten ändert, muss der Benutzer vorher bestätigen.

Der Server ist ein Intel NUC 14 Pro (Core Ultra 7 155H, Arc-Grafik im Prozessor, 32 GB RAM), auf dem auch die
übrigen Dienste der Homecloud laufen.

## Entscheidung

**Name:** Uke. Im Judo ist Uke der Partner, an dem Tori die Technik übt: Er arbeitet mit, setzt aber nichts gegen
den Willen des anderen durch. „Kano“ (nach dem Gründer des Judo) haben wir bewusst nicht genommen.

**Sprachmodell als eigener Dienst:** `llama.cpp` (`llama-server`) aus dem offiziellen Image
`ghcr.io/ggml-org/llama.cpp:server-vulkan`, als zweiter Container im Stack. Es ist nur im internen Docker-Netz
erreichbar, ohne Traefik-Route.
- Er nutzt die Arc-Grafik über Vulkan (`/dev/dri`), ohne Grafik läuft er nur auf der CPU, dann langsamer.
- Modell: **Qwen3-30B-A3B Instruct 2507** (4 Bit, `Q4_K_M`, etwa 18 GB plus Kontext, Speichergrenze 24 GB),
  Werkzeugaufrufe im OpenAI-Format (`--jinja`), ohne Denk-Modus. Der Container lädt das Modell beim ersten Start in
  ein eigenes Volume.
- Es ist ein Mixture-of-Experts-Modell, das je Token nur etwa 3 Milliarden Parameter rechnet. Es schreibt deshalb
  schneller als ein dichtes 8B-Modell und ist trotzdem genauer.
- Zuerst lief Qwen3 8B: Im Test mit Beispieldaten erkannte es „bald“, „der nächste“ und Wettkämpfe zuverlässiger als
  Qwen3 4B, auf dem NUC schrieb es aber nur etwa 10 Tokens pro Sekunde, und die Antworten waren mittelmäßig.
- Qwen3 8B (etwa 6 GB) bleibt die Ausweichlösung, wenn der Speicher knapp wird.
- Eine Cloud (IONOS AI Model Hub) haben wir erwogen und verworfen: Daten bleiben lokal.
- Kleine Modelle verketten Werkzeuge ungern. Deshalb liefert `termine_suchen` bei höchstens drei Treffern die
  Teilnehmer gleich mit, wenn der Benutzer sie sehen darf.
- Links, die das Modell selbst schreibt, entfernt das Portal, weil sie oft erfunden sind. Emojis auch.
- Eigener Container statt im Portal-Image: Das Portal-Image bleibt klein, Renovate aktualisiert beide getrennt, der
  Modell-Dienst hat eine eigene Speichergrenze und ein Absturz trifft das Portal nicht. Ist er nicht erreichbar,
  antwortet Uke mit einem Hinweis, alles andere läuft weiter.
- Das Portal spricht ihn über `PORTAL_ASSISTANT_URL` an (OpenAI-kompatibles `/v1/chat/completions`). Leer heißt:
  Uke ist aus, es gibt keinen Menüpunkt. `fake` liefert feste Antworten für E2E-Tests und die Demo.

**Werkzeuge statt Datenbankzugriff** (`portal/assistant/tools.py`):
- Das Modell sieht keine Datenbank und keine Seiten, nur eine Liste von Werkzeugen mit Beschreibung. Es schlägt
  Aufrufe vor, das Portal führt sie aus und gibt das Ergebnis als JSON zurück.
- Jedes Werkzeug ruft nur Services der Fach-Apps auf, mit dem angemeldeten Benutzer (`events.agenda`,
  `can_see_participants` …), ohne eigene Fachlogik. So sieht Uke genau das, was der Benutzer auch auf den Seiten
  sieht. Werkzeuge, die der Benutzer nicht nutzen darf, werden ihm gar nicht erst angeboten.
- Höchstens vier Werkzeug-Runden je Frage, Eingaben auf 500 Zeichen und 60 Fragen je Stunde begrenzt.
- In der ersten Runde jeder Frage muss das Modell ein Werkzeug aufrufen (`tool_choice: required`). Sonst beantwortet
  es Rückfragen wie „Montag ist nicht der 01.12.“ aus dem Verlauf und rät dabei. Das kostet eine Runde, auch bei
  „Danke“.
- Wochentage rechnet das Modell nicht selbst um: Der Systemprompt enthält die nächsten 14 Tage als Kalender, und
  `termine_suchen` filtert mit `wochentag`.
- Die Uhrzeit steht vor der aktuellen Frage, nicht im Systemprompt. So bleiben Systemprompt und Werkzeuge den ganzen
  Tag gleich, und `llama-server` muss sie dank Prompt-Cache nicht bei jeder Frage neu einlesen.
- Texte aus den Werkzeugen (Hinweise, Beschreibungen) sind laut Systemprompt nur Daten. Das allein schützt nicht
  sicher vor Prompt Injection. Deshalb gilt die nächste Regel.

**Ändern nur mit Bestätigung im Portal (folgt im nächsten Schritt):**
- Schreibende Werkzeuge führen nichts aus, sondern legen einen Vorschlag an. Der Chat zeigt ihn als Karte mit
  „Bestätigen“ und „Abbrechen“.
- Erst der Klick führt den Service aus, als normales Formular mit CSRF-Schutz und erneuter Rechteprüfung. Ein „Ja“
  im Chat genügt nicht, damit kein Text in den Daten das Modell zu einer Änderung bringen kann.
- In der ersten Version gibt es nur lesende Werkzeuge: Termine suchen, Termin-Details und die Hilfe durchsuchen.

**Verlauf:**
- Fragen und Antworten werden 30 Tage gespeichert (`Conversation`, `Message`) und dann nächtlich gelöscht.
- Die Chat-Seite zeigt nur das laufende Gespräch der Sitzung. Alles Gespeicherte steht in der Datenauskunft
  (`privacy.export_user`).
- Mit dem Zugang werden auch die Gespräche gelöscht. Tonaufnahmen werden nie gespeichert, wenn später die Sprache
  dazukommt.
- An das Modell gehen nur die letzten acht Nachrichten des Gesprächs. Die Antworten der Werkzeuge werden nicht
  gespeichert.

**Oberfläche:** Uke erreicht man von jeder Seite über einen runden Knopf unten rechts (DaisyUI `fab`). Er öffnet
ein **nicht-modales** Chat-Fenster (`<dialog>` mit `show()`, Inhalt mit DaisyUI `chat`).
- Nicht-modal, weil man mit Uke neben der Seite arbeitet: Man fragt, folgt einem Termin-Link und fragt weiter. Ein
  modales Fenster würde die Seite sperren und den Gedankengang unterbrechen.
- Am Desktop schwebt das Fenster unten rechts und öffnet sich nach einem Seitenwechsel wieder, mit demselben
  Gespräch aus der Sitzung.
- Am Handy füllt es den Bildschirm, weil daneben kein Platz ist. Ein Link schließt es dann. Der Knopf sitzt dort
  über der Aktionsleiste und verschwindet bei offener Seitenleiste.
- Escape oder ✕ schließen das Fenster, der Fokus springt zurück auf den Knopf.
- Die Seite `/uke/` bleibt für Links und als Ersatz ohne JavaScript. Einen eigenen Menüpunkt gibt es nicht.
- Ohne JavaScript schickt ein normales Formular die Frage ab.
- Mit `static/js/uke.js` erscheinen Frage und „denkt nach“ sofort, die Antwort kommt als HTML-Schnipsel.
- Antworten zeigt das Portal maskiert, mit nur **fett** und Listen.
- Termine nennt das Modell mit einer Marke aus den Werkzeugen, z. B. „Kindertraining am Montag, 30.11., um 17 Uhr
  [T12]“. Das Portal prüft die Marken beim Speichern: Erfundene fallen weg, aus echten wird ein kleiner Link „Termin →“
  direkt im Text.
- Datum und Wochentag im selben Absatz oder Listenpunkt setzt das Portal auf die des Termins. Modelle verrechnen sich
  bei Wochentagen; so stimmt das Datum neben einem Link immer.
- Steht die Marke allein („Trainer beim [T12] ist Anna“), zeigt der Link Titel, Tag und Uhrzeit aus der Datenbank.
- Unter der Antwort stehen nur gefundene Termine und Hilfe-Kapitel, die der Text nicht schon nennt. So steht nichts
  doppelt da, und wenn das Modell die Marken vergisst, fehlen die Links trotzdem nicht. Alle Links stammen aus dem
  Portal, nicht vom Modell, und stimmen deshalb immer.

## Konsequenzen

- Antworten dauern einige Sekunden. Das Modell rechnet eine Frage nach der anderen, weitere warten. Für einen Verein
  reicht das.
- Kleine Modelle irren sich, zum Beispiel bei Namen oder Tagen. Die Links unter der Antwort und später die
  Bestätigungskarten zeigen immer die echten Daten.
- Neue Funktionen bekommen ein Werkzeug nur, wenn es einen Service dafür gibt. Fachlogik nur für Uke gibt es nicht.
- Im Stack der Homecloud kommt ein Dienst mit Volume für das Modell und Zugriff auf `/dev/dri` dazu. Das Portal
  bekommt `PORTAL_ASSISTANT_URL`.

## Verworfene Alternativen

- **Cloud-Modelle** (z. B. OpenAI oder Anthropic): besser und schneller, aber Fragen mit Namen von Kindern würden den
  Verein verlassen.
- **Modell im Portal-Container** (z. B. `llama-cpp-python` im Gunicorn-Prozess): Das Image wäre mehrere GB groß, der
  einzige Worker wäre blockiert, und Speichergrenzen ließen sich nicht trennen.
- **Ollama:** bequem, aber ein weiterer eigener Modellspeicher. `llama-server` reicht und kann Vulkan.
- **Freier Datenbankzugriff für das Modell** (Text-zu-SQL): Rechte wären nicht sicher durchzusetzen.
- **Spracherkennung im Browser** (Web Speech API): Chrome schickt die Aufnahmen an Google. Für Sprache folgt
  whisper.cpp auf dem Server.
- **Verlauf im Portal anzeigen:** vorerst nicht gewünscht, nur in der Auskunft.
- **Modales Overlay** (DaisyUI `modal`): sperrt die Seite und schließt beim Navigieren, passt nicht zu Fragen
  neben der Arbeit.
- **Eigener Menüpunkt in der Seitenleiste:** doppelt zum Knopf, der auf jeder Seite da ist.
