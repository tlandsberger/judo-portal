# 0017 – Einheitliche Bedienung von Listen und Detailseiten

- Status: angenommen
- Datum: 2026-11-17

## Kontext

Einträge ließen sich auf verschiedene Arten öffnen: mal über den Titel, mal über einen Stift-Button, manchmal über
beides. Löschen stand mal in der Liste, mal im Kopf der Detailseite, mal am Seitenende. Die Benutzerliste hatte eine
Reihe von Icon-Buttons für Aktionen, die selten gebraucht werden.

## Entscheidung

1. **Liste → Eintrag:** Der Titel bzw. Name ist der Link zum Eintrag (`link link-hover font-semibold`), ohne
   Detailseite direkt zur Bearbeiten-Seite. Kein zusätzlicher Stift- oder „Bearbeiten“-Button in der Zeile.
2. **Schnellaktionen in der Zeile nur für häufige Fälle** (z. B. Stunden bestätigen, Teilnehmer austragen).
   Seltenes wie Einladung erneut senden oder Deaktivieren steht am Eintrag selbst.
3. **Entfernen aus einer Zuordnung** (Teilnehmer, fest eingeteilt, Verknüpfung, offene Einladung, Passkey) bleibt in
   der Zeile, weil es den Eintrag nicht löscht: `btn btn-outline btn-sm` mit Text („Entfernen“, „Lösen“ …).
4. **Löschen eines Eintrags** nie in Listen, sondern am Ende der Detail- bzw. Bearbeiten-Seite:
   `btn btn-ghost btn-error btn-sm` mit `bi-trash` und „… löschen“. Ebenso Benutzer deaktivieren.
5. **Detailseite:** im Kopf `btn btn-outline btn-primary btn-sm` mit `bi-pencil` und „Bearbeiten“.
6. **Bearbeiten-Seite:** oben Zurück-Link (`bi-arrow-left` + Ziel), unten „Speichern“ (`btn-primary`) und
   „Abbrechen“ (`btn`).

## Konsequenzen

- Einträge öffnet man überall gleich; die Zeilen bleiben ruhig, auch auf dem Handy.
- Löschen braucht einen Schritt mehr (Eintrag öffnen) und passiert dadurch seltener versehentlich.
- Offene Einladungen haben keine eigene Seite; ihre Aktionen bleiben deshalb in der Zeile.
