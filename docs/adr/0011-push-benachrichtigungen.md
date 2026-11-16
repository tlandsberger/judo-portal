# 0011 – Push-Benachrichtigungen mit Mail als Ersatz

- Status: angenommen
- Datum: 2026-11-15

## Kontext

Bisher ging jede Nachricht per Mail. Für den Vereinsalltag ist das zu schwerfällig: Eine Absage am Nachmittag oder
eine Erinnerung zum Bestätigen soll direkt aufs Handy kommen. Das Portal ist bereits eine installierbare PWA mit
Service Worker; eine App im Store wollen wir nicht pflegen.

## Entscheidung

### Kanäle

| Was | Kanal |
|---|---|
| Einladung, Anmeldecode | immer Mail |
| Sicherheit des Zugangs: Passwort gesetzt/geändert, Passkey hinzugefügt/entfernt, Anmeldung auf neuem Gerät | immer Mail |
| Neue Verknüpfung mit einem Mitglied | immer Mail |
| Alles an Gäste (ohne Benutzer, ADR 0013) | immer Mail |
| Tägliches: Termin abgesagt oder geändert, Nachgerückt, Anmeldung offen, Erinnerung Anmeldeschluss, Stunden bestätigen | Push, sonst Mail |

- Hat ein Benutzer mindestens ein Gerät mit Push, kommt Tägliches nur per Push.
- Nimmt keines seiner Geräte die Nachricht an, geht sie per Mail raus. Abgelaufene Abos (HTTP 404/410) werden dabei
  gelöscht.
- Weitere Einstellungen gibt es bewusst nicht: Push lässt sich je Gerät ein- und ausschalten, das ist alles.
- Jede Benachrichtigung hat einen Schlüssel (z. B. `registration_open:<termin>:<benutzer>`) und geht nur einmal raus.
  Eltern mit mehreren Kindern bekommen eine Nachricht mit allen Namen.
- Das Versandprotokoll (`SentNotification`) wird nach 90 Tagen gelöscht.

### Technik

- **Web Push mit VAPID** über `pywebpush`.
  - Den Schlüssel geben `PORTAL_VAPID_PUBLIC_KEY` und `PORTAL_VAPID_PRIVATE_KEY` vor, erzeugt mit
    `manage.py generate_vapid_keys`.
  - Ohne Schlüssel ist Push aus, und alles geht per Mail.
- **App `portal.notifications`:**
  - Abos je Gerät, `notify()` mit Ersatz per Mail, Aktionsknöpfe
  - Abschnitt „Benachrichtigungen“ unter „Meine Anmeldung“, Hinweis auf der Startseite
  - Sie kennt nur `portal.accounts`. Die Fach-Apps rufen `notify()` auf und melden Aktionen über `register_action` an.
- **Aktionsknöpfe** („Anmelden“, „Doch absagen“, „Bestätigen“):
  - Jeder Knopf trägt einen mit Django `signing` signierten Token: Benutzer, Aktion, Daten, 7 Tage gültig.
  - Der Service Worker schickt ihn an `/benachrichtigungen/aktion/`. Der Token ersetzt Sitzung und CSRF-Token.
  - Ausgeführt wird über die Services der Fach-App, mit denselben Prüfungen wie in der Oberfläche: Rechte,
    Anmeldezeitraum, Zielgruppe, Höchstzahl.
  - Die Aktionen sind idempotent.
  - Safari (iPhone/iPad) und Firefox zeigen keine Knöpfe; dort öffnet der Tipp die passende Seite.
- **Aussehen:** In der Nachricht steht das App-Icon. In der Statusleiste (Android) zeigt ein eigenes Badge die beiden
  Figuren des Signets (`badge-96.png` aus `scripts/make_icons.py`); Android nutzt davon nur die Form.
- **Zeitplaner:** `portal.core.scheduler` führt neben dem nächtlichen Job alle 10 Minuten kurze Jobs aus.
  - Fach-Apps melden sie über `register_periodic` und `register_daily` an.
  - Die Jobs der Veranstaltungen: Anmeldung offen, Erinnerung 24 h vor Anmeldeschluss, Stunden bestätigen (am Abend
    des Termins, bei späten Terminen am nächsten Morgen).
- **Neues Gerät:**
  - Bei jeder Anmeldung wird ein Fingerabdruck des Browsers gespeichert (`KnownDevice`): ein Hash des User-Agents ohne
    Versionsnummern, nicht der User-Agent selbst.
  - Ist der Browser neu und der Benutzer schon von anderswo bekannt, geht eine Warnung per Mail raus.
  - Während der Einrichtung nach einer Einladung gibt es keine Sicherheitsmails.

## Konsequenzen

- **Datenschutz:**
  - Push-Inhalte sind Ende-zu-Ende-verschlüsselt (RFC 8291). Die Push-Dienste von Google, Apple und Mozilla sehen nur
    Metadaten.
  - Die Texte bleiben knapp: Name des Kindes, Termin, Ort; kein Gewicht, keine Kontaktdaten.
- Auf iPhone/iPad geht Push nur, wenn das Portal zum Home-Bildschirm hinzugefügt ist (iOS ab 16.4). Die Oberfläche
  sagt das.
- Der Versand läuft synchron nach dem Commit, Push mit 10 Sekunden Timeout je Gerät. Für die Größe der Abteilung
  reicht das; eine Queue brauchen wir nicht.
- Wechselt das VAPID-Schlüsselpaar, verfallen alle Abos. Die Benutzer müssen Push dann neu einschalten.

## Verworfene Alternativen

- **Native App:** Store-Konten, Reviews und zwei Codebasen – zu viel Pflege.
- **ntfy/Gotify:** eigene App auf jedem Handy nötig und Themen statt Benutzer; Aktionsknöpfe ohne Anmeldung wären
  schwer abzusichern.
- **Einstellungen je Anlass:** mehr Oberfläche, wenig Nutzen; bei Bedarf später ergänzbar.
