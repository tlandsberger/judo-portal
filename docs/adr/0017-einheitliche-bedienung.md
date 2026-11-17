# 0017 – Einheitliche Bedienung: Listen, Detailseiten und Schaltflächen

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
   `btn btn-ghost btn-error` mit `bi-trash` und „… löschen“. Ebenso Benutzer deaktivieren.
5. **Detailseite:** im Kopf `btn btn-outline btn-primary` mit `bi-pencil` und „Bearbeiten“.
6. **Bearbeiten-Seite:** oben Zurück-Link (`bi-arrow-left` + Ziel), unten „Speichern“ (`btn-primary`) und
   „Abbrechen“ (`btn`).

### Schaltflächen

**Größe nach Ebene:**

- **Normal** (`btn`) auf Seitenebene: Seitenkopf, Absenden von Formularen (auch in Karten), Filterleisten,
  Löschen am Seitenende, Bestätigungsseiten.
- **Klein** (`btn-sm`) nur in Listenzeilen, im Kopf eines Abschnitts (neben `card-title`, z. B. „+ Termin“),
  in Hinweisleisten und bei der Seitennavigation von Listen.
- **Groß** (`btn-lg`) nur für die eine Hauptaktion auf Anmeldung und Einladung.

**Aussehen nach Gewicht:**

| Rolle | Klassen | Beispiele |
| --- | --- | --- |
| Hauptaktion (höchstens eine je Bereich) | `btn-primary` | Speichern, Anlegen, Einreichen, Anmelden |
| Weitere Aktion | `btn-outline btn-primary` | Bearbeiten, Datenauskunft, Unterseiten im Seitenkopf |
| Neutral | `btn` | Abbrechen, Filter „Anzeigen“, Zurückgeben |
| Nebenaktion | `btn-ghost` | Nein danke, Nicht dabei?, Hilfe vor/zurück |
| Zeile: positiv / sonst | `btn-primary btn-sm` / `btn-outline btn-sm` | Anmelden, Bestätigen / Entfernen, Abmelden, Verwalten |
| Löschen, Deaktivieren am Eintrag | `btn-ghost btn-error` | … löschen, Benutzer deaktivieren |
| Absagen (umkehrbar, wichtig) | `btn-outline btn-error` | Absagen, Termine im Zeitraum absagen |
| Endgültig auf der Bestätigungsseite | `btn-error` | Endgültig löschen |

**Position:** Im Seitenkopf rechts neben dem Titel (auf dem Handy darunter), Hauptaktion zuerst. Titel und
Aktionen stehen in einer Zeile, die Beschreibung darunter in voller Breite – sonst schiebt ein langer Text den
Button aus der Kopfzeile. In den Kopf gehören nur die Hauptaktionen der Seite (z. B. „… anlegen“); Links zu
Unterseiten wie Rollen oder Veranstaltungsarten stehen unter dem Inhalt. In Formularen
unten links: Hauptaktion, dann „Abbrechen“. Löschen allein am Seitenende. In Zeilen rechts.

**Icons:** Seitenkopf- und Abschnittsaktionen mit Icon und Text; „Speichern“/„Abbrechen“ ohne Icon. In Zeilen nur
Text, reine Icon-Buttons (`btn-square`) nur mit `aria-label` und `title`.

Die Seite „Bausteine“ (`/bausteine/`) zeigt die Varianten.

## Konsequenzen

- Einträge öffnet man überall gleich; die Zeilen bleiben ruhig, auch auf dem Handy.
- Löschen braucht einen Schritt mehr (Eintrag öffnen) und passiert dadurch seltener versehentlich.
- Offene Einladungen haben keine eigene Seite; ihre Aktionen bleiben deshalb in der Zeile.
