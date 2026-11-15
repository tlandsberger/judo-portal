# Wedeler TSV Judo – Vereinsportal

Vereinsportal der Judo-Abteilung im Wedeler TSV e.V.: Mitglieder, Eltern, Übungsleiter und Abteilungsleitung
melden sich an und finden alles Vereinsrelevante an einem Ort. Läuft im Browser und lässt sich auf dem Handy als App
installieren. Produktiv unter **https://judo.tlandsberger.de**.

## Stand

- **Fundament:** Anmeldung mit Passkey, Passwort oder Code per E-Mail, Zugänge nur per Einladung, Rollen,
  Benutzerverwaltung, Erscheinungsbild nach dem Design System „Wedeler TSV Judo“ (hell und dunkel).
- **Als Nächstes:** Mitgliederverwaltung mit CSV-Import und Zugängen für Mitglieder und Eltern, danach Termine und
  Übungsleiterabrechnung. Jedes Feature wird vorher fachlich geplant.

## Technik auf einen Blick

| Bereich | Technik |
|---|---|
| Anwendung | Django 6 (Python 3.15), eine App pro Fachbereich |
| Oberfläche | Bootstrap 5.3 mit WTSV-Theme, htmx, PWA |
| Anmeldung | django-allauth: Passkeys, Passwort, Anmeldecode per Mail |
| Daten | SQLite im Volume, nächtliche Backups |
| Betrieb | ein Docker-Container, Homecloud (Portainer, Traefik, Cloudflare-Tunnel) |
| Wartung | Renovate, CI mit Unit-, E2E-, Barrierefreiheits- und Screenshot-Tests, wöchentliches Release |

Details: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), Entscheidungen: [`docs/adr/`](docs/adr/),
Betrieb: [`docs/betrieb.md`](docs/betrieb.md).

## Entwickeln

Voraussetzungen: [uv](https://docs.astral.sh/uv/) und Node.js 24.

```bash
uv sync                      # Python-Abhängigkeiten
npm ci && npm run vendor     # Bootstrap, Icons, htmx, Schrift nach portal/static/vendor kopieren
export PORTAL_DEBUG=true PORTAL_INITIAL_ADMIN_EMAIL=du@example.org
uv run python manage.py migrate
uv run python manage.py bootstrap_admin   # Einladungslink erscheint auf der Konsole
uv run python manage.py runserver         # http://localhost:8000
```

Prüfen wie die CI:

```bash
uv run ruff format --check . && uv run ruff check . && uv run mypy portal && uv run pytest
```

E2E-Tests gegen das Docker-Image: [`e2e/README.md`](e2e/README.md).

## Mitarbeiten

Commits folgen den [Conventional Commits](https://www.conventionalcommits.org/de/) (`feat:`, `fix:`, `docs:` …),
die CI prüft das. Daraus entstehen jeden Sonntag automatisch Version, Changelog und Image.
