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
- Modell: **Qwen3 8B** (4 Bit, `Q4_K_M`, etwa 5 GB), Werkzeugaufrufe im OpenAI-Format (`--jinja`), ohne
  Denk-Modus. Der Container lädt das Modell beim ersten Start in ein eigenes Volume.
- Im Test mit Beispieldaten hat das 8B-Modell „bald“, „der nächste“ und Wettkämpfe zuverlässiger erkannt als Qwen3 4B
  (Instruct 2507). Das 4B-Modell bleibt die Ausweichlösung, wenn `manage.py assistant_benchmark` auf dem NUC zu
  langsam ist (siehe `docs/betrieb.md`).
- Kleine Modelle verketten Werkzeuge ungern. Deshalb liefert `termine_suchen` bei höchstens drei Treffern die
  Teilnehmer gleich mit, wenn der Benutzer sie sehen darf.
- Links, die das Modell selbst schreibt, entfernt das Portal, weil sie oft erfunden sind.
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

**Oberfläche:** Seite „Uke“ in der Seitenleiste für alle Benutzer, mit DaisyUI-`chat`.
- Ohne JavaScript schickt ein normales Formular die Frage ab.
- Mit `static/js/uke.js` erscheinen Frage und „denkt nach“ sofort, die Antwort kommt als HTML-Schnipsel.
- Antworten zeigt das Portal maskiert, mit nur **fett** und Listen.
- Unter der Antwort stehen Links zu den Terminen und Hilfe-Kapiteln, die die Werkzeuge gefunden haben. Diese Links
  stammen aus den Werkzeugen, nicht vom Modell, und stimmen deshalb immer.

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
