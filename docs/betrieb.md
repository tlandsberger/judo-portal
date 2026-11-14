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
| `PORTAL_EMAIL_FROM` | ja | `WTSV Judo <portal@tlandsberger.de>` | Absender |
| `PORTAL_DATA_DIR` | – | `/data` | Datenbank und Backups |
| `PORTAL_BACKUP_HOUR` / `PORTAL_BACKUP_KEEP_DAYS` | – | `2` / `14` | nächtliches Backup |
| `PORTAL_SECURE_COOKIES` | – | `true` | nur für lokale Tests ohne HTTPS auf `false` |
| `PORTAL_DEBUG` | – | `false` | nur Entwicklung |

Ohne `PORTAL_EMAIL_HOST` gehen Mails auf die Konsole (Container-Log), mit `PORTAL_EMAIL_FILE_PATH` in Dateien.

## Erster Start

1. Container mit den Variablen oben starten (in der Homecloud: Portainer-Stack anlegen).
2. Der Container migriert die Datenbank und lädt `PORTAL_INITIAL_ADMIN_EMAIL` als Administrator ein. Der Link steht
   zusätzlich im Container-Log, falls die Mail nicht ankommt.
3. Link öffnen → „Einladung annehmen“ → Passkey und/oder Passwort einrichten.
4. Unter **Konten** weitere Personen einladen (z. B. die Abteilungsleitung).

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

## Überwachung

- `GET /healthz` (Docker-Healthcheck im Image).
- Täglicher Live-Check in GitHub Actions, sobald die Repository-Variable `LIVE_URL` gesetzt ist.

## Einmalige Einstellungen auf GitHub

1. **Default-Branch** auf `main` stellen (Settings → General). Entwicklung über Pull Requests nach `main`.
2. **Renovate-App** für das Repo freischalten (wie in der Homecloud).
3. Nach dem ersten Release das Paket `judo-portal` unter Packages auf **public** stellen.
4. Variable **`LIVE_URL`** = `https://judo.tlandsberger.de` setzen (Settings → Secrets and variables → Actions).
