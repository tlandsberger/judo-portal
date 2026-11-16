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
- **Eine Abrechnung (`Claim`) je Übungsleiter und Monat**, einzureichen nach Monatsende.
  - Ein noch offener Monat ist kein Datensatz, sondern wird aus den bestätigten Teilnahmen berechnet.
  - **Frist:** der 10. (Kalendertag) des dritten Folgemonats, z. B. Januar bis 10. April (`deadline`).
  - **Ausnahmen:** Auch nach der Frist lässt sich einreichen. Die Abrechnung ist dann als verspätet markiert
    (`is_late`), und die Abteilungsleitung entscheidet beim Freigeben über die Ausnahme. Die Markierung entsteht beim
    ersten Einreichen; wird eine fristgerecht eingereichte Abrechnung nach der Frist zurückgegeben, bleibt sie
    fristgerecht.
- **Ablauf:** eingereicht → freigegeben oder zurückgegeben (mit Pflicht-Rückmeldung) → erneut eingereicht.
  - Die Abteilungsleitung darf auch ihre eigene Abrechnung freigeben. Es gibt nicht immer eine Vertretung; das
    Vier-Augen-Prinzip liegt bei der Geschäftsstelle. Das PDF nennt, wer freigegeben hat.
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
  Admins), Entscheidung an den Übungsleiter. Am 3. eines Monats ab 9 Uhr Erinnerung an den Vormonat und an den
  Monat, dessen Frist am 10. endet; je Monat und Anlass nur einmal.
- Die Übungsleiterpauschale (§ 3 Nr. 26 EStG) überwacht das Portal nicht.

## Konsequenzen

- Fehlende Sätze fallen beim Einreichen auf, nicht erst bei der Geschäftsstelle.
- Abrechnungen bleiben dauerhaft erhalten; Löschfristen folgen mit den Datenschutz-Funktionen (Roadmap 5).
- „Meine Stunden“ zeigt vergangene Termine bis zur Frist zurück (135 Tage).
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
