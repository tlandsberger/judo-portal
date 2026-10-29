# 0009 – Zugänge per Einladung über die Keycloak-Admin-API

- Status: angenommen
- Datum: 2026-10-29

## Kontext

Mitglieder (ab 14 Jahren) und Eltern minderjähriger Mitglieder sollen das Portal nutzen und dort nur ihre eigenen
Daten bzw. die ihrer Kinder sehen. Dazu braucht es Benutzerkonten in Keycloak und eine eindeutige Zuordnung
Konto ↔ Mitglied. Eltern sind dabei keine eigene Rolle, sondern einfach Konten, die mit ihren Kindern verknüpft
sind. Selbstregistrierung würde die Zuordnung von der Qualität der E-Mail-Adressen in der Mitgliederliste abhängig
machen; manuelle Pflege in der Keycloak-Konsole wäre zu viel Handarbeit.

## Entscheidung

- **Einladung aus dem Portal:** Abteilungsleiter und Administrator laden pro Mitglied ein – den eigenen Zugang
  (ab 14) oder Erziehungsberechtigte (nur für Minderjährige). Das Backend legt das Konto in Keycloak an und
  lässt Keycloak eine Mail „Passwort festlegen + E-Mail bestätigen“ schicken (Execute-Actions-Mail, 7 Tage gültig,
  danach geht es ins Portal). Gibt es zur E-Mail schon ein bestätigtes Konto, wird nur verknüpft.
- **Service-Account mit minimalen Rechten:** vertraulicher Client `judo-portal-backend`, nur
  `realm-management`: `manage-users`, `view-users`, `query-users`. Das Secret kommt per Umgebungsvariable
  (`PORTAL_KEYCLOAK_CLIENT_SECRET`). Aufruf mit Spring `RestClient` und Client-Credentials-Token, gekapselt hinter
  `AccountDirectory` (Modul `shared`) – keine Keycloak-Bibliothek im Fachcode.
- **Verknüpfung im Portal:** Tabelle `member_access` (Keycloak-`sub`, `SELF` oder `GUARDIAN`). Der eigene Zugang
  bekommt die Realm-Rolle `member`, Eltern keine Rolle. Alle anderen Rollen vergibt weiterhin der Administrator in
  Keycloak.
- **Sichtbarkeit wird bei jedem Zugriff geprüft:** Eltern sehen ihr Kind bis zum Tag vor dem 18. Geburtstag;
  danach ist der Zugang „abgelaufen“, ohne dass jemand etwas tun muss. Mitglieder und Eltern dürfen nur lesen.
- **Mails:** Keycloak verschickt über den SMTP-Server des Realms. Lokal und in Tests fängt Mailpit alle Mails ab;
  der produktive Mailserver wird mit dem Deployment (Schritt 9) festgelegt.

## Konsequenzen

- ➕ Eindeutige Zuordnung Konto ↔ Mitglied, kein Abgleich über E-Mail-Adressen nötig.
- ➕ Passwort, E-Mail-Bestätigung, Passwort-Reset und Brute-Force-Schutz bleiben bei Keycloak.
- ➕ Das Backend kann nur Benutzer verwalten, keine Realm-Einstellungen oder Clients ändern.
- ➖ Das Backend hängt für Einladungen von Keycloak und dem Mailversand ab; Fehler werden als 502 mit deutscher
  Meldung gezeigt und können wiederholt werden.
- ➖ Ein Secret mehr im Betrieb. Wird ein Mitglied gelöscht, bleibt das Keycloak-Konto bestehen (nur die
  Verknüpfung entfällt).

## Verworfene Alternativen

- **Selbstregistrierung mit Abgleich per E-Mail:** weniger Aufwand, aber falsche oder doppelte Adressen in der
  Mitgliederliste führen zu falschen Zuordnungen – bei Kinderdaten nicht vertretbar.
- **Manuelle Konten in der Keycloak-Konsole:** kein Mailserver nötig, aber viel Handarbeit und fehleranfällig.
- **Keycloak Admin Client (Java-Bibliothek):** zieht RESTEasy und viele Abhängigkeiten nach sich; die wenigen
  Aufrufe sind mit `RestClient` überschaubar.
- **Eigene Rolle „Erziehungsberechtigte“:** unnötig, weil sich die Rechte aus der Verknüpfung ergeben.
