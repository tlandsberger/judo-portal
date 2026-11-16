# 0013 – Gäste

- Status: angenommen
- Datum: 2026-11-16

## Kontext

Manche Veranstaltungen richten sich auch an Externe: offene Lehrgänge, Freundschaftsturniere, Probetrainings. Gäste
haben keinen Zugang zum Portal (Zugänge gibt es nur per Einladung, ADR 0002). Sie sollen trotzdem auf der
Teilnehmerliste stehen und ihre eigenen Angaben jederzeit sehen können.

## Entscheidung

- **Gast** (`Guest`) je Veranstaltung:
  - Felder: Name, Jahrgang, Geschlecht, Graduierung, Gewicht, Verein, E-Mail, Telefon für Notfälle, bei
    Minderjährigen Erziehungsberechtigte, Zeitpunkt der Zustimmung zum Datenschutzhinweis.
  - Die Teilnahme je Termin steht wie bei Mitgliedern in `Participation` (genau eins von Mitglied oder Gast), immer
    mit der „Rolle bei Anmeldung“.
- **Nur bei „Gäste willkommen“** an der Veranstaltung.
  - Zielgruppen gelten nach Jahrgang, Geschlecht, Graduierung und Gewicht; Interessen werden bei Gästen nicht geprüft.
  - Gäste zählen zur Höchstzahl und kommen sonst auf die Warteliste.
- **Zwei Wege:**
  1. **Das Team trägt ein** („Gast eintragen“ auf dem Termin): sofort gültig, auch nach dem Anmeldeschluss und über
     die Höchstzahl hinaus (Ausnahme). Der Gast bekommt eine Mail mit seinem Link.
  2. **Öffentlicher Anmeldelink** der Veranstaltung (`/gaeste/anmelden/<schlüssel>/`), den die Abteilungsleitung teilt
     und neu erzeugen kann:
     - Auswahl der offenen Termine, Daten, Datenschutzhinweis mit Zustimmung.
     - **Double-Opt-in:** Die Anmeldung gilt erst nach Bestätigung über den Link in der Mail und zählt vorher nicht zur
       Höchstzahl. Unbestätigte Gäste werden nach 24 Stunden gelöscht (Job alle 5 Minuten).
     - **Spam-Schutz:** Honeypot-Feld und höchstens 10 Anmeldungen je IP-Adresse und Stunde.
- **Gast-Seite** `/gast/<schlüssel>/` ohne Anmeldung: Termine mit Status, Ort und Hinweis; Anmeldung bestätigen,
  absagen (bis zum Anmeldeschluss), weitere offene Termine; eigene Daten ändern. Jede Mail an den Gast enthält den Link.
  Das Bestätigen ist ein Knopf (POST), damit Mail-Scanner nichts auslösen.
- **Benachrichtigungen** an Gäste immer per Mail: Bestätigung, Willkommen, Absage, Änderung, Nachrücken.
- **Datenschutz:**
  - Gastdaten werden 90 Tage nach dem letzten Termin des Gastes gelöscht (nächtlicher Job).
  - Sehen können sie die Abteilungsleitung und das Team der Termine, in der Teilnehmerliste mit Notfallkontakt.

## Konsequenzen

- Erste öffentliche Seiten des Portals (ohne Anmeldung). Die Schlüssel sind zufällig (`secrets.token_urlsafe`) und
  nicht erratbar. Wer den Link eines Gastes hat, sieht dessen Daten; der Link steht nur in Mails an den Gast.
- Ein Gast, der zu mehreren Veranstaltungen kommt, gibt seine Daten je Veranstaltung neu ein. Das hält das Modell
  einfach und die Löschfrist eindeutig.

## Verworfene Alternativen

- **Gäste als Mitglieder anlegen:** vermischt Vereinsdaten mit Externen und macht die Löschung schwierig.
- **Zugang für Gäste:** Einladung, Passwort oder Passkey für einen einzelnen Lehrgang sind zu viel Aufwand.
- **Captcha:** braucht einen externen Dienst (keine externen CDNs); Honeypot, Begrenzung und Double-Opt-in reichen.
