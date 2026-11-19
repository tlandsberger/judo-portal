# 0026 – Ferien und Feiertage (Termine fallen aus)

- Status: angenommen
- Datum: 2026-11-19
- Ergänzt: [0012](0012-teilnahme-mit-rollen.md)

## Kontext

Trainings laufen über Zeitpläne. In Schulferien und an Feiertagen fallen viele davon aus, aber nicht alle: Ein
Wettkampftraining läuft vielleicht in den Herbstferien weiter. Bisher sagte die Abteilungsleitung je Veranstaltung
einen Zeitraum ab („Termine absagen“), jedes Jahr neu und ohne gemeinsamen Rückweg. Die Zeiträume selbst einzutragen
ist mühsam; schulferien.org bietet sie als iCal-Datei an.

## Entscheidung

- **Ferien und Feiertage** (`Closure`, in der Oberfläche nur „Ferien und Feiertage“, ein Eintrag z. B. „Herbstferien“;
  anfangs „Schließzeiten“ genannt): eine benannte Gruppe von Zeiträumen (`ClosurePeriod`, von–bis), z. B. „Herbstferien“
  mit den Herbstferien aller Jahre oder „Gesetzliche Feiertage“ mit allen Feiertagen.
- **Import aus iCal** (`closures.parse`, Paket `icalendar`): Die Abteilungsleitung lädt die Dateien von
  schulferien.org hoch (Ferien und Feiertage), sieht eine Vorschau (neu, geändert, vorhanden) und übernimmt.
  - Einträge mit „ferien“ im Namen werden je Ferienart ein Eintrag; Jahr und Bundesland fallen aus dem Namen
    des Eintrags weg, der Zeitraum behält das Jahr („Herbstferien 2026“). Alle übrigen Einträge landen in
    „Gesetzliche Feiertage“.
  - Ganztägige Einträge enden laut iCal am Folgetag (exklusiv); das Portal speichert den letzten Tag.
  - Doppeltes wird an der UID erkannt, sonst am Zeitraum, weil schulferien.org bei jedem Export neue UIDs vergibt.
    Geänderte Ferien (gleiche UID) werden angepasst.
  - Hochladen statt Abruf über einen Link: Der Server braucht keinen Zugriff nach außen, und einmal im Jahr zwei
    Dateien hochzuladen ist wenig Aufwand.
  - Zeiträume ohne Import (z. B. ein Brückentag) lassen sich von Hand anlegen.
- **Auswahl am Zeitplan** (`Schedule.closures`): beliebige Einträge je Zeitplan (Feld „Fällt aus in“).
- **Abgleich** (`closures.sync`): Kommende Termine des Zeitplans in einem ihrer Zeiträume werden
  abgesagt und merken sich den Zeitraum (`Occurrence.closure_period`). Liegt ein so abgesagter Termin nicht mehr in
  einem ausgewählten Zeitraum (Zeitraum gelöscht, Eintrag am Zeitplan abgewählt), findet er wieder statt. Abgeglichen wird
  nach Import, Änderungen an Zeiträumen oder Einträgen, beim Speichern eines Zeitplans und wenn das Portal neue
  Termine erzeugt.
  - Von Hand abgesagte Termine (ohne Zeitraum) bleiben unberührt.
  - „Findet doch statt“ an einem Termin in den Ferien oder an einem Feiertag setzt `closure_exempt`; der Abgleich sagt ihn dann
    nicht wieder ab.
- **Nachrichten** über `notify` (ADR 0011): an Angemeldete und eingeteilte Übungsleiter, gebündelt je Benutzer und
  Eintrag („Herbstferien: 3 Termine fallen aus“), ebenso beim Wiederaufnehmen. Gäste bekommen je Termin eine
  Mail wie bei einer Absage. Wer nicht angemeldet ist, sieht „fällt aus: Herbstferien“ unter „Termine“.
- Absagen und Wiederaufnahmen, Import und Löschen stehen im Protokoll.

## Konsequenzen

- Neue Python-Abhängigkeit `icalendar` (reines Python).
- Neue Seiten „Ferien und Feiertage“ und „Importieren“ (Abteilungsleitung), Feld „Fällt aus in“ am Zeitplan.
- Einzelne Ausfälle laufen weiter über „Termine absagen“ an der Veranstaltung.
- Vergangene Termine ändert der Abgleich nie.

## Verworfene Alternativen

- **Massenabsage über mehrere Veranstaltungen:** einfacher, aber ohne gemeinsamen Rückweg und ohne Wirkung auf Termine,
  die erst später erzeugt werden.
- **Feiertage selbst berechnen** (Paket `holidays`): eine weitere Abhängigkeit; schulferien.org liefert die Feiertage
  im selben Format wie die Ferien.
- **Abruf über einen iCal-Link:** bräuchte Zugriff nach außen und eine Prüfung, ob die Quelle noch passt.
