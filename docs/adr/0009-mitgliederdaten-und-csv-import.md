# 0009 – Mitgliederdaten, Zugänge und CSV-Import

- Status: angenommen
- Datum: 2026-11-15

## Kontext

Die Mitgliederverwaltung (`portal.members`) setzt ADR 0003 um. Offen war:
- welche Daten wir speichern,
- wie sie ins Portal kommen,
- wie Mitglieder und Eltern einen Zugang bekommen.

Die Stammdaten führt weiterhin der Hauptverein. Das Portal braucht nur, was Training und Abteilung nutzen.

## Entscheidung

### Daten

- Name, Geburtsdatum, Geschlecht.
- Mitgliedsnummer, Eintritt und Austritt.
- E-Mail und Telefon, optional.
- Aktuelle Graduierung (9. Kyu bis 10. Dan) **ohne Prüfungshistorie**.
- Gewicht in kg mit einer Nachkommastelle. Die Gewichtsklasse ergibt sich später aus Alter, Geschlecht und Gewicht;
  wir speichern sie nicht.
- **Nicht gespeichert:** Adresse, Pass- bzw. Lizenznummer, Bankdaten.

### Rechte

| Wer | Darf |
|---|---|
| Abteilungsleitung, Administrator | alles sehen und ändern, importieren, Zugänge geben |
| Übungsleiter | vorerst keinen Zugriff auf Mitglieder (siehe unten) |
| Benutzer mit Verknüpfung | unter „Meine Daten“ das eigene Profil und die Kinder unter 18 sehen; E-Mail, Telefon, Graduierung und Gewicht selbst ändern |

### Ein Benutzer mit mehreren Mitgliedern

- Es gibt kein Umschalten zwischen Profilen; die Rechte gelten pro Mitglied.
- „Meine Daten“ führt bei einem Mitglied direkt zu dessen Seite.
- Bei mehreren zeigt „Meine Daten“ eine Übersicht: das eigene Profil zuerst, dann die Kinder vom ältesten zum jüngsten.
- Spätere Bereiche (z. B. Termine) gruppieren ihre Einträge genauso nach Mitglied.

### Zugänge

- Die Abteilungsleitung gibt Zugänge auf der Seite des Mitglieds: für das Mitglied selbst ab 14 oder für einen
  Elternteil, solange das Mitglied unter 18 ist.
- **Neue Adresse:** Es geht eine Einladung raus. Die Verknüpfung ist dabei vorgemerkt (`PendingLink`) und entsteht,
  wenn die Einladung angenommen wird. Mehrere Kinder an dieselbe Adresse landen in einer Einladung.
- **Adresse mit Benutzer:** Der Benutzer wird direkt verknüpft und per Mail benachrichtigt.
- Wer sein eigenes Profil verknüpft, bekommt die Rolle „Mitglied“. Eltern bekommen keine Rolle.
- `portal.accounts` kennt die Mitglieder nicht. Die Verknüpfung entsteht über das Signal `invitation_accepted`
  (`portal/accounts/signals.py`).

### CSV-Import

- Ablauf in zwei Schritten: Hochladen mit Vorschau (neu, geändert, unverändert, Fehler), dann Übernehmen.
- Abgleich über die Mitgliedsnummer.
- Leere Zellen überschreiben nichts. Mitglieder, die nicht in der Datei stehen, bleiben unverändert; der Import löscht
  nie.
- Unbekannte Spalten werden ignoriert. Die Datei liegt bis zur Bestätigung in der Sitzung.

### Trainingsgruppen später

Trainingsgruppen (wer trainiert wo, welche Übungsleiter gehören dazu) planen wir gesondert. Bis dahin haben
Übungsleiter keinen Zugriff auf Mitglieder (außer auf ihre eigenen Daten unter „Meine Daten“). Mit den Gruppen
bekommen sie Zugriff auf die Mitglieder ihrer Gruppen.

## Konsequenzen

- ➕ Wenig sensible Daten und kein zweites Verwaltungssystem neben dem Hauptverein.
- ➕ Der Import lässt sich gefahrlos wiederholen, selbst gepflegte Werte bleiben erhalten.
- ➖ Austritte erkennt der Import nicht von selbst. Dafür trägt die Datei das Austrittsdatum, oder die Abteilungsleitung
  pflegt es selbst.
- ➖ Graduierungen dürfen Mitglieder und Eltern selbst ändern. Wir vertrauen darauf; ein Änderungsprotokoll folgt mit
  Roadmap-Schritt 5.

## Verworfene Alternativen

- **Prüfungshistorie:** fachlich nicht gebraucht, mehr Pflegeaufwand.
- **Gewichtsklasse als Freitext:** wird mit Alter und Regeländerungen falsch. Das Gewicht bleibt richtig.
- **Profil-Umschalter für Eltern:** mehr Bedienschritte und fehleranfällig. Die Übersicht zeigt alles auf einen Blick.
- **Import löscht fehlende Mitglieder:** zu gefährlich bei unvollständigen Exporten.
