# 0020 – Schnellzugang per Code, Quick-Link und QR-Code

- Status: angenommen
- Datum: 2026-11-18

## Kontext

Ausschreibungen für Lehrgänge, Wettkämpfe oder besondere Trainings gehen als PDF oder Aushang herum. Bisher mussten
Mitglieder den Termin im Portal selbst suchen. Ein kurzer Code, ein Link und ein QR-Code auf der Ausschreibung sollen
direkt zur Anmeldung führen.

## Entscheidung

- **Modell `QuickLink`** mit einem `code` und genau einem Ziel: einem Termin oder einer Veranstaltung
  (CheckConstraint). Der Code entsteht beim ersten Anzeigen (`quicklinks.code_for`), deshalb braucht es keine
  Datenmigration für bestehende Termine.
- **Code:** 6 Zeichen aus `23456789ABCDEFGHJKMNPQRSTUVWXYZ` (ohne 0/O und 1/I/L), zufällig mit `secrets`.
  Groß-/Kleinschreibung, Leerzeichen und Bindestriche spielen bei der Eingabe keine Rolle. Bei rund 900 Millionen
  Möglichkeiten und Login-Pflicht ist Raten kein Thema.
- **Quick-Link** `/q/<code>/` mit Login-Pflicht. Ohne Anmeldung geht es zum Login und danach weiter. Externe
  Teilnehmer nutzen weiter ihren eigenen Anmeldelink (ADR 0013).
  - Termin: die Termin-Seite.
  - Veranstaltung: „Termine“, gefiltert auf die Veranstaltung und ohne „Nur passende“, damit auch Termine
    erscheinen, die gerade nicht passen (bei einer Empfehlung kann man sich trotzdem anmelden, ADR 0019).
- **Code eingeben:** kleines Feld oben auf „Termine“ (`/q/?code=…`). Ein unbekannter Code ergibt „Code nicht
  gefunden.“
- **QR-Code** auf dem Server mit **segno** (reines Python, keine weiteren Abhängigkeiten), schwarz auf weiß, als SVG
  zum Anzeigen und als SVG oder PNG zum Herunterladen. Er enthält den vollständigen Quick-Link mit
  `PORTAL_BASE_URL`, damit er unabhängig davon stimmt, über welche Adresse man gerade im Portal ist. Ausgeliefert über
  eigene Views, also ohne Inline-Inhalt (CSP).
- **Sichtbar** ist der Schnellzugang auf der Veranstaltung für die Abteilungsleitung und am Termin für alle, die ihn
  leiten (`can_lead`).

## Konsequenzen

- Codes bleiben gültig, solange der Termin bzw. die Veranstaltung existiert; sie werden mit ihnen gelöscht.
- Neue Python-Abhängigkeit `segno` (Renovate hält sie aktuell).

## Verworfene Alternativen

- **Code als Feld an Termin und Veranstaltung:** zwei getrennte Namensräume und eine Datenmigration für Bestehendes.
- **QR-Code im Browser erzeugen:** braucht eine JavaScript-Bibliothek und liefert keine Datei für die Ausschreibung.
- **Quick-Link ohne Login mit Formular für Externe:** Externe haben schon den Gäste-Anmeldelink; ein zweiter
  öffentlicher Weg wäre doppelt.
