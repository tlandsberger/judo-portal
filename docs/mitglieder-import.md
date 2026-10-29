# Mitgliederliste importieren

Die bisherige Excel-Liste lässt sich als CSV ins Portal übernehmen – einmalig oder wiederholt.
Importieren darf der **Abteilungsleiter** (Mitglieder → „Importieren“).

## Datei vorbereiten

1. Liste in Excel öffnen, **Datei → Speichern unter**, Dateityp **„CSV UTF-8 (durch Trennzeichen getrennt)“**.
   Das klassische „CSV (Trennzeichen-getrennt)“ funktioniert auch (Umlaute werden erkannt).
2. Die erste Zeile muss die Spaltenüberschriften enthalten. Reihenfolge egal, weitere Spalten werden ignoriert:

| Spalte | Pflicht | Hinweis |
|---|---|---|
| Mitgliedsnr | ja | Schlüssel für den Abgleich, darf in der Datei nur einmal vorkommen |
| Anrede | nein | `Herr`/`Hr.` → männlich, `Frau`/`Fr.` → weiblich; sonst Geschlecht im Portal nachtragen |
| Name, Vorname | ja | |
| Geburtsdatum | ja | `TT.MM.JJJJ` |
| Telefon privat, E-Mail | nein | |
| Vereinseintritt | ja | `TT.MM.JJJJ` |
| Vereinsaustritt | nein | `TT.MM.JJJJ` |

Beispiel mit Fantasiedaten: [beispiel-mitgliederliste.csv](beispiel-mitgliederliste.csv).

## Was beim Import passiert

- Erst kommt eine **Vorschau**: neu, geändert (mit Feldern), unverändert, Fehler (mit Zeilennummer und Grund).
  Gespeichert wird erst mit „Import ausführen“.
- **Neue Nummern** werden als aktive Mitglieder angelegt.
- **Bekannte Nummern** werden aktualisiert. Für ihre Spalten gilt die Datei: eine leere Zelle leert das Feld.
  Ein im Portal gesetztes Geschlecht wird nie gelöscht. Adresse und Aktiv/Passiv stehen nicht in der Datei
  und bleiben unverändert.
- Mitglieder, die **nicht in der Datei** stehen, bleiben unberührt (es wird nichts gelöscht).
- **Fehlerzeilen** werden übersprungen; nach der Korrektur in Excel einfach erneut importieren.
- Die Datei (höchstens 1 MB) wird nur verarbeitet, nicht gespeichert.
