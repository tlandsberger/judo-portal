# 0014 – Übungsleiterabrechnung

- Status: angenommen
- Datum: 2026-11-16

## Kontext

Übungsleiter bestätigen nach jedem Termin ihre Stunden bei abrechnungsrelevanten Rollen (ADR 0012). Bisher wurde
außerhalb des Portals abgerechnet. Die Geschäftsstelle des Hauptvereins braucht je Übungsleiter und Monat eine
Aufstellung, die die Abteilungsleitung freigegeben hat. Ausgezahlt wird weiterhin außerhalb des Portals.

## Entscheidung

- **Eigene App `portal.billing`**, die nur über `portal.events.services` und Modelle auf Teilnahmen zugreift.
- **Stundensätze (`Rate`) je Mitglied und Rolle**, explizit, ohne Grundsatz, mit „gültig ab“.
  - Es gilt der Satz, der am Termintag gültig ist.
  - Ohne Satz lässt sich eine Rolle für diese Person nicht abrechnen; das Einreichen nennt die fehlenden Rollen.
  - Gepflegt von der Abteilungsleitung (Seite „Stundensätze“).
  - **Rolle nur mit Satz** (November 2026): Eine abrechnungsrelevante Rolle kann nur übernehmen, wer dafür am Termintag
    (bei Zeitplänen und neuen Veranstaltungen: heute) einen Satz hat. Ohne Satz bietet der Termin die Rolle nicht
    zum Übernehmen oder Vertreten an, und Eintragen, Übertragen und feste Einteilung lehnen sie mit Hinweis auf die
    Seite „Stundensätze“ ab. Bestehende Einteilungen bleiben. `portal.events` kennt die Sätze nicht: `billing`
    meldet die Prüfung über `events.services.register_role_check` an; `can_take_role` und `role_unavailable`
    fragen alle angemeldeten Prüfungen ab.
- **Bestätigen und Anpassen** (November 2026): Stunden bestätigt man nur auf der Startseite, unter „Meine Abrechnung“
  oder aus der Benachrichtigung, nicht am Termin; dort steht nur, ob sie bestätigt sind. Weicht etwas ab, öffnet
  „Anpassen“ (bei bestätigten Zeilen der Stift in der Tabelle des Monats) ein Formular mit Übungsleiter, Rolle und Dauer
  (`events.services.adjust_hours`). Eigene Dauer und Rolle gelten danach als bestätigt. Ein anderer Übungsleiter
  übernimmt den Platz wie beim Übertragen und bestätigt seine Stunden selbst. Das Formular bietet nur
  abrechnungsrelevante Rollen an, für die ein Satz gilt. „Bestätigung zurücknehmen“ bleibt als Knopf in der Tabelle.
- **Eine Abrechnung (`Claim`) je Übungsleiter und Monat**, einzureichen nach Monatsende.
  - Ein noch offener Monat ist kein Datensatz, sondern wird aus den bestätigten Teilnahmen berechnet.
  - **Frist:** der 5. (Kalendertag) des dritten Folgemonats, z. B. Januar bis 5. April (`deadline`).
  - **Ausnahmen:** Auch nach der Frist lässt sich einreichen. Die Abrechnung ist dann als verspätet markiert
    (`is_late`), und die Abteilungsleitung entscheidet beim Freigeben über die Ausnahme. Die Markierung entsteht beim
    ersten Einreichen; wird eine fristgerecht eingereichte Abrechnung nach der Frist zurückgegeben, bleibt sie
    fristgerecht.
- **Ablauf:** eingereicht → freigegeben oder zurückgegeben (mit Pflicht-Rückmeldung) → erneut eingereicht.
  - Die Abteilungsleitung darf auch ihre eigene Abrechnung freigeben. Es gibt nicht immer eine Vertretung; das
    Vier-Augen-Prinzip liegt bei der Geschäftsstelle. Das PDF nennt, wer freigegeben hat.
  - **Reklamation nach der Freigabe** (November 2026): Findet die Geschäftsstelle noch Mängel, gibt die
    Abteilungsleitung auch eine freigegebene Abrechnung mit Rückmeldung zurück. Weil schon ein PDF weitergegeben sein
    kann, fragt ein Dialog vorher nach (DaisyUI-Modal; ohne JavaScript zeigt der Server den Dialog). Die Abrechnung
    merkt sich die zurückgenommene Freigabe (`corrected_from`); nach erneutem Einreichen und Freigeben trägt sie die
    Markierung „korrigiert“, und das PDF ist als „korrigierte Abrechnung“ gekennzeichnet, mit dem Datum der ersetzten
    Freigabe. Die CSV hat dafür hinten die Spalten „Korrigiert“ und „Ersetzt Freigabe vom“. Protokolliert als
    `reopen`.
- **Prüfansicht** (November 2026): Für die Abteilungsleitung alle eingereichten und freigegebenen Zeilen eines Monats
  über alle Übungsleiter, nach Termin gruppiert (`services.review`). Markiert sind abgesagte Termine und Zeilen mit
  mehr Minuten, als der Termin dauert; so fallen unplausible Abrechnungen vor der Freigabe auf.
- **Schnappschuss:** Beim Einreichen werden Datum, Veranstaltung, Rolle, Minuten, Satz und Betrag als `ClaimLine`
  gespeichert. Spätere Änderungen an Terminen, Rollen oder Sätzen ändern eingereichte Abrechnungen nicht.
  - Betrag je Zeile kaufmännisch auf Cent gerundet (`Decimal`).
  - `ClaimLine.participation` und `Claim.member` sind `PROTECT`: Abgerechnetes lässt sich nicht versehentlich löschen.
- **Sperre:** Solange ein Monat eingereicht oder freigegeben ist, lassen sich seine Termine nicht bestätigen, die
  Dauer nicht ändern und die Rolle nicht wechseln.
  - `portal.events` kennt die Abrechnung nicht: `billing` meldet in `ready()` eine Prüfung über
    `events.services.register_lock` an, wie beim Zeitplaner.
  - Bis zum Einreichen lassen sich bestätigte Minuten korrigieren (erneutes `confirm`).
- **Ausgabe:**
  - PDF je freigegebener Abrechnung mit `fpdf2`, eingebaute Helvetica mit Windows-1252 (Umlaute, €). Mit
    Unterschriftszeilen für Übungsleiter und Geschäftsstelle.
  - CSV je Monat mit allen freigegebenen Abrechnungen (Semikolon, UTF-8 mit BOM für Excel).
- **Benachrichtigungen** über `notify` (ADR 0011): eingereicht an die Abteilungsleitung (ohne Abteilungsleitung an
  Admins), Entscheidung an den Übungsleiter. Am 1. eines Monats ab 9 Uhr Erinnerung an den Vormonat und an den
  Monat, dessen Frist am 5. endet; je Monat und Anlass nur einmal.
- Die Übungsleiterpauschale (§ 3 Nr. 26 EStG) überwacht das Portal nicht.

## Konsequenzen

- Fehlende Sätze fallen beim Einreichen auf, nicht erst bei der Geschäftsstelle.
- Abrechnungen bleiben dauerhaft erhalten; Löschfristen folgen mit den Datenschutz-Funktionen (Roadmap 5).
- „Meine Abrechnung“ zeigt oben unter „Noch bestätigen“ alle vergangenen, unbestätigten Termine der offenen Monate;
  die Seite „Meine Stunden“ gibt es nicht mehr (November 2026), kommende Einteilungen stehen unter „Termine“.
- PDF und CSV weisen verspätete Abrechnungen aus, damit die Geschäftsstelle die Ausnahme sieht.
- Neue Python-Abhängigkeit `fpdf2` (reines Python, braucht kein System-Paket im Image).

## Verworfene Alternativen

- **Grundsatz je Person mit Abweichungen je Rolle:** weniger Pflege, aber ein vergessener Rollensatz würde still mit
  dem Grundsatz abgerechnet.
- **Satz je Rolle für alle:** passt nicht zu Sätzen nach Lizenz.
- **Ausnahme vorab freischalten** (Abteilungsleitung öffnet einen Monat je Person): ein Schritt mehr für beide
  Seiten; die Entscheidung beim Freigeben genügt.
- **Freigabe nur durch eine andere Person:** blockiert, wenn es keine Vertretung gibt.
- **Druckansicht im Browser statt PDF:** uneinheitlich je Browser, kein fester Dateiname für die Ablage.
- **WeasyPrint/ReportLab:** WeasyPrint braucht System-Bibliotheken (Pango) im Image; ReportLab ist für eine Tabelle
  unnötig groß.
