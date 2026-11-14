# 0004 – SQLite statt Datenbankserver

- Status: angenommen
- Datum: 2026-11-14

## Kontext

Das Portal hat wenige hundert Mitglieder und wenige gleichzeitige Nutzer. Ein Datenbankserver bedeutet einen
weiteren Container, Passwörter, Updates und eigene Backups.

## Entscheidung

- **SQLite** als Datei im Volume (`/data/portal.sqlite3`), WAL-Modus, `IMMEDIATE`-Transaktionen, Busy-Timeout.
- **Backup:** Die App schreibt täglich um 02:00 einen konsistenten Schnappschuss (SQLite-Backup-API) nach
  `/data/backups/` (14 Tage). Das restic-Backup der Homecloud sichert das Volume um 02:30 (lokal und OneDrive).
- Ein Gunicorn-Worker mit Threads; der Zeitplaner läuft als Thread in diesem Worker.
- Wechsel zu PostgreSQL bleibt über das ORM möglich, falls Last oder Funktionen es erfordern.

## Konsequenzen

- ➕ Kein Datenbank-Container, Backup und Wiederherstellung sind Dateioperationen.
- ➖ Nur ein schreibender Prozess sinnvoll; lange Schreibtransaktionen vermeiden.
