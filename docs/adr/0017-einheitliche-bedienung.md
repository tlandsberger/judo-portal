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
4. **Löschen eines Eintrags** nie in Listen, sondern auf der Detail- bzw. Bearbeiten-Seite im Menü „Weitere
   Aktionen“, rot und als letzter Punkt. Ebenso Benutzer deaktivieren und Termin absagen.
5. **Detailseite:** „Bearbeiten“ (`bi-pencil`) ist die Hauptaktion im Seitenkopf.
6. **Bearbeiten-Seite:** Zurück-Link im Seitenkopf, am Formularende „Speichern“ (`btn-primary`) und „Abbrechen“
   (`btn`) in der Aktionsleiste.

### Seitenkopf und Aktionen

Alle Seiten der App erweitern `layouts/page.html` (Blöcke `back_url`/`back_label`, `heading`, `heading_extra`,
`primary`, `more`, `more_forms`, `intro`, `page`). Damit sieht der Kopf überall gleich aus und steht nie in einer
Karte: Zurück-Link, Titel mit Hilfe oder Badges, rechts die Aktionen, darunter die Beschreibung.

- **Höchstens eine Hauptaktion** (`btn-primary`, Block `primary`), z. B. „… anlegen“, „Bearbeiten“, „PDF
  herunterladen“.
- **Alles andere im Menü „Weitere Aktionen“** (⋯, DaisyUI-`dropdown` mit `menu`, Block `more`): Unterseiten
  (Rollen, Veranstaltungsarten, Stundensätze …), Datenauskunft, Export, Abmelden und zuletzt rot das Gefährliche
  („… löschen“, „Termin absagen“, „Benutzer deaktivieren“). POST-Aktionen als `<li><button form="…">` mit dem
  versteckten Formular im Block `more_forms`.
- **Am Handy steht die Hauptaktion unten** in der Aktionsleiste (`.action-bar` in `portal/assets/app.css`): fest
  am unteren Rand über die ganze Breite, immer an derselben Stelle und mit dem Daumen erreichbar. Oben bleiben nur
  Titel und ⋯, nichts bricht um. Ab `md` steht sie im Kopf bzw. am Formularende.
- **Formulare** (eines je Seite) legen „Speichern“ und „Abbrechen“ in eine `.action-bar`; am Handy steht
  „Abbrechen“ links, die Hauptaktion rechts. Kleinere Formulare in Abschnitten (Telefon, Hinweis, Satz eintragen)
  bleiben normale Buttons im Abschnitt.
- **Abschnitts- und Zeilenaktionen** bleiben klein im Abschnitt bzw. in der Zeile (siehe unten).

### Schaltflächen

**Größe nach Ebene:**

- **Normal** (`btn`) auf Seitenebene: Seitenkopf, Aktionsleiste, Absenden von Formularen (auch in Karten),
  Filterleisten, Bestätigungsseiten.
- **Klein** (`btn-sm`) nur in Listenzeilen, im Kopf eines Abschnitts (neben `card-title`, z. B. „+ Termin“),
  in Hinweisleisten und bei der Seitennavigation von Listen.
- **Groß** (`btn-lg`) nur für die eine Hauptaktion auf Anmeldung und Einladung.

**Aussehen nach Gewicht:**

| Rolle | Klassen | Beispiele |
| --- | --- | --- |
| Hauptaktion (höchstens eine je Bereich) | `btn-primary` | Speichern, Anlegen, Einreichen, Anmelden |
| Weitere Aktion im Inhalt | `btn-outline btn-primary` | Nur Link erstellen, Hinweis speichern, Abschnittsaktionen |
| Neutral | `btn` | Abbrechen, Filter „Anzeigen“, Zurückgeben |
| Nebenaktion | `btn-ghost` | Nein danke, Nicht dabei?, Hilfe vor/zurück |
| Zeile: positiv / sonst | `btn-primary btn-sm` / `btn-outline btn-sm` | Anmelden, Bestätigen / Entfernen, Abmelden, Verwalten |
| Löschen, Deaktivieren, Absagen am Eintrag | Menüpunkt `text-error` | … löschen, Benutzer deaktivieren, Termin absagen |
| Absagen im Inhalt (umkehrbar, wichtig) | `btn-outline btn-error` | Termine im Zeitraum absagen |
| Endgültig auf der Bestätigungsseite | `btn-error` | Endgültig löschen |

**Position:** siehe „Seitenkopf und Aktionen“. In Zeilen stehen Aktionen rechts.

**Icons:** Seitenkopf- und Abschnittsaktionen mit Icon und Text; „Speichern“/„Abbrechen“ ohne Icon. In Zeilen nur
Text, reine Icon-Buttons (`btn-square`) nur mit `aria-label` und `title`.

Die Seite „Bausteine“ (`/bausteine/`) zeigt die Varianten.

## Konsequenzen

- Einträge öffnet man überall gleich; die Zeilen bleiben ruhig, auch auf dem Handy.
- Löschen braucht einen Schritt mehr (Eintrag öffnen) und passiert dadurch seltener versehentlich.
- Offene Einladungen haben keine eigene Seite; ihre Aktionen bleiben deshalb in der Zeile.
