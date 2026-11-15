# Betrieb

Das Portal läuft als **ein Docker-Container** (`ghcr.io/tlandsberger/judo-portal`) mit einem Volume für `/data`.
Produktiv in der Homecloud (Repo `tlandsberger/homecloud`, Stack `application/judo-portal`).

## Umgebungsvariablen

| Variable | Pflicht | Beispiel / Standard | Bedeutung |
|---|---|---|---|
| `PORTAL_SECRET_KEY` | ja | `openssl rand -base64 48` | Geheimschlüssel (Sitzungen, Tokens) |
| `PORTAL_BASE_URL` | ja | `https://judo.tlandsberger.de` | Öffentliche Adresse (Links in Mails, CSRF) |
| `PORTAL_ALLOWED_HOSTS` | ja | `judo.tlandsberger.de` | erlaubte Hostnamen, kommagetrennt |
| `PORTAL_INITIAL_ADMIN_EMAIL` | beim ersten Start | `du@example.org` | wird als Administrator eingeladen, solange es keinen aktiven gibt |
| `PORTAL_EMAIL_HOST` | ja | `smtp.ionos.de` | SMTP-Server |
| `PORTAL_EMAIL_PORT` | – | `587` | |
| `PORTAL_EMAIL_USER` / `PORTAL_EMAIL_PASSWORD` | ja | Postfach-Zugang | |
| `PORTAL_EMAIL_USE_TLS` | – | `true` | STARTTLS |
| `PORTAL_EMAIL_FROM` | ja | `Wedeler TSV Judo <portal@tlandsberger.de>` | Absender |
| `PORTAL_DATA_DIR` | – | `/data` | Datenbank und Backups |
| `PORTAL_BACKUP_HOUR` / `PORTAL_BACKUP_KEEP_DAYS` | – | `2` / `14` | nächtliches Backup |
| `PORTAL_SECURE_COOKIES` | – | `true` | nur für lokale Tests ohne HTTPS auf `false` |
| `PORTAL_TRUSTED_PROXIES` | – | private Netze | Proxys (Traefik), deren `X-Forwarded-For` als echte Client-IP gilt |
| `PORTAL_DEBUG` | – | `false` | nur Entwicklung |
| `PORTAL_VERSION` | – | aus dem Image | setzt der Release-Workflow beim Bauen; steht in der Fußzeile (Link auf die Release-Notes) |

Ohne `PORTAL_EMAIL_HOST` gehen Mails auf die Konsole (Container-Log), mit `PORTAL_EMAIL_FILE_PATH` in Dateien.

## Erster Start

1. Container mit den Variablen oben starten (in der Homecloud: Portainer-Stack anlegen).
2. Der Container migriert die Datenbank und lädt `PORTAL_INITIAL_ADMIN_EMAIL` als Administrator ein. Der Link steht
   zusätzlich im Container-Log, falls die Mail nicht ankommt.
3. Link öffnen → „Einladung annehmen“ → Passkey und/oder Passwort einrichten.
4. Unter **Benutzer** weitere Personen einladen (z. B. die Abteilungsleitung).

### Einladungen und Mail-Scanner

Mailfilter (z. B. Microsoft Safe Links) öffnen Links in einer Sandbox und klicken dort sogar Buttons. Deshalb gibt
„Einladung annehmen“ nur eine **Einrichtungs-Sitzung** (30 Minuten): Erst mit einem eingerichteten Passkey oder
Passwort gibt es Zugang, und nur für die Sitzung, die ihn eingerichtet hat. Bis dahin bleibt der Link 7 Tage gültig
und kann beliebig oft geöffnet werden. Wer keinen Passkey und kein Passwort will, wählt „Lieber per Code anmelden“.

- **Link ohne Mail:** unter Benutzer → „Nur Link erstellen“ bzw. „Link kopieren“ (erzeugt jeweils einen neuen Link).
- **Rettungsweg** ohne Oberfläche (z. B. wenn keine Mail ankommt):
  ```bash
  docker exec judo_portal python manage.py invite du@example.org --admin --no-mail   # Link wird ausgegeben
  ```
- Der erste Administrator wird beim Neustart erneut eingeladen, solange er seinen Zugang nicht eingerichtet hat und
  die alte Einladung abgelaufen ist.

## Mitglieder importieren

Unter **Mitglieder → CSV-Import** (Abteilungsleitung, Administrator). Zuerst kommt eine Vorschau, gespeichert wird erst
mit „Übernehmen“. Regeln und Hintergründe stehen in ADR 0009.

| Spalte | Pflicht | Format |
|---|---|---|
| Mitgliedsnummer | ja | Abgleich mit bestehenden Mitgliedern |
| Vorname, Nachname | ja | |
| Geburtsdatum | ja | `TT.MM.JJJJ` oder `JJJJ-MM-TT` |
| Geschlecht | | `w`, `m` oder `d` |
| Eintritt, Austritt | | Datum wie oben; wer ein Austrittsdatum in der Vergangenheit hat, gilt als ausgetreten |
| E-Mail, Telefon | | |
| Graduierung | | z. B. `5. Kyu`, `1. Dan` |
| Gewicht | | kg, z. B. `32,5` |

- Trennzeichen ist Semikolon oder Komma. Unbekannte Spalten werden ignoriert.
- Kodierung UTF-8 oder Windows/Excel (cp1252). Die Vorlage gibt es auf der Import-Seite.
- Leere Zellen überschreiben nichts.
- Mitglieder, die nicht in der Datei stehen, bleiben unverändert. Der Import löscht nie.

### Zugänge für Mitglieder und Eltern

Auf der Seite des Mitglieds → **Zugang geben**:
- **Für das Mitglied selbst:** ab 14.
- **Für einen Elternteil:** bis 18. Die Verknüpfung endet automatisch mit dem 18. Geburtstag.

Was dann passiert:
- **Die Adresse hat schon einen Benutzer:** Er wird direkt verknüpft und bekommt eine kurze Mail.
- **Die Adresse ist neu:** Es geht eine Einladung raus, verknüpft wird beim Annehmen.

Einen Elternteil mit mehreren Kindern lädst du nacheinander für jedes Kind ein. Das ergibt eine einzige Einladung.

## Backup und Wiederherstellung

- Täglich um 02:00 schreibt die App `portal-JJJJ-MM-TT.sqlite3` nach `/data/backups/` (14 Tage). Das restic-Backup
  der Homecloud sichert das Volume um 02:30. Sofort-Backup: `docker exec judo_portal python manage.py backup_db`.
- Wiederherstellen:
  ```bash
  docker stop judo_portal
  # im Volume: Backup an die Stelle der Datenbank kopieren und WAL-Dateien entfernen
  cp backups/portal-2026-11-14.sqlite3 portal.sqlite3 && rm -f portal.sqlite3-wal portal.sqlite3-shm
  docker start judo_portal
  ```

## Updates und Releases

- Jeden Sonntag 23:00 entsteht automatisch ein Release, wenn es neue Commits gibt (Version, Changelog, Image).
  Manuell: GitHub → Actions → „Release“ → „Run workflow“.
- Renovate aktualisiert danach das Image in der Homecloud; Patch und Minor werden automatisch gemergt, Portainer
  deployt. Datenbank-Migrationen laufen beim Start des Containers.
- Zurückrollen: Image-Tag in der Homecloud auf die Vorversion setzen. Bei neuen Migrationen vorher aus dem Backup
  wiederherstellen.

## Client-IP hinter dem Reverse-Proxy

Das Portal ersetzt die Verbindungsadresse (Traefik) durch die echte Quell-IP aus `X-Forwarded-For`: von rechts der
erste Eintrag, der kein vertrauenswürdiger Proxy ist (`PORTAL_TRUSTED_PROXIES`). Andere Header, etwa
`CF-Connecting-IP`, wertet es nicht aus. Die IP erscheint unter „Meine Anmeldung → Angemeldete Geräte“ und zählt für
die Sperre gegen Durchprobieren.

Der Proxy muss den Header vertrauenswürdig setzen. In der Homecloud übernimmt Traefik das `X-Forwarded-For` von
Cloudflare nur aus dem Netz `cloudflare` (`forwardedHeaders.trustedIPs` am Eingang `cloudflare`) und setzt es am
LAN-Eingang selbst, siehe README im Repo `homecloud`.

## Überwachung

- `GET /healthz` (Docker-Healthcheck im Image).
- Täglicher Live-Check in GitHub Actions, sobald die Repository-Variable `LIVE_URL` gesetzt ist.

## Einmalige Einstellungen auf GitHub

1. **Default-Branch** auf `main` stellen (Settings → General). Entwicklung über Pull Requests nach `main`.
2. **Renovate-App** für das Repo freischalten (wie in der Homecloud).
3. Nach dem ersten Release das Paket `judo-portal` unter Packages auf **public** stellen.
4. Variable **`LIVE_URL`** = `https://judo.tlandsberger.de` setzen (Settings → Secrets and variables → Actions).
