# CLAUDE.md – judo-portal

Vereinsportal „WTSV Judo“ (Django, eine App pro Fachbereich). Architektur: `docs/ARCHITECTURE.md`,
Entscheidungen: `docs/adr/`, Betrieb: `docs/betrieb.md`.

## Arbeitsweise

- Pro Feature werden die fachlichen Anforderungen geplant und freigegeben; danach freie Hand bei der Umsetzung.
  Vorher melden nur bei offenen fachlichen Fragen, Auswirkungen auf den Betrieb (Homecloud, Datenbank, Mail) oder
  nicht umkehrbaren Schritten (Release, Merge, Löschen).
- Technische Entscheidungen trifft Claude selbst und hält sie als ADR fest.
- Doku, Kommentare und Oberflächentexte auf Deutsch (Du-Form), Code-Bezeichner englisch.

## Befehle

```bash
uv sync && npm ci && npm run vendor
PORTAL_DEBUG=true uv run python manage.py runserver
uv run ruff format . && uv run ruff check --fix . && uv run mypy portal && uv run pytest
uv run python manage.py makemigrations          # nach Modelländerungen, Migration mit committen
```

E2E (Docker nötig): siehe `e2e/README.md`. Nach gewollten Design-Änderungen die Screenshots mit
`--update-snapshots` im Playwright-Container neu erzeugen und committen.

## Regeln

- **Commits:** Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `ci:`, `chore:` …). `feat` = Minor,
  `fix` = Patch, `!`/`BREAKING CHANGE` = Major. Die CI prüft das, das Release entsteht daraus automatisch.
- **Module:** neue Fachbereiche als eigene App unter `portal/<bereich>/` (Modelle, Services, Views, Templates, Tests).
  Fachlogik in `services.py`, Views schlank. Querverweise zwischen Apps nur über deren Services/Modelle, nicht über Views.
- **Rechte:** fest definierte Rollen in `portal/accounts/models.py` (`Role`). Prüfen auf dem Server mit
  `role_required` bzw. `user.has_role(...)` (`portal/accounts/permissions.py`). Anzeige in Templates spiegelt das.
- **Konten und Mitglieder sind getrennt;** Verknüpfungen (eigenes Profil, Erziehungsberechtigt …) sind m:n.
- **Anmeldung:** django-allauth; Passkey, Passwort und Mail-Code sind gleichwertig (kein erzwungener zweiter Faktor,
  siehe `PortalAccountAdapter`). Keine Selbstregistrierung, Zugänge nur per Einladung.
- **Oberfläche:** Bootstrap-Klassen plus `portal/static/css/theme.css`. Farben nur über die Theme-Variablen
  (`--wtsv-*`, `--bs-*`), beide Themes (hell/dunkel) prüfen. Vereins-Piktogramme als `.pikto .pikto-<name>`,
  Bedien-Icons aus Bootstrap Icons. App-Icon und Favicons nur über `scripts/make_icons.py` erzeugen
  (`uv run --with pillow python scripts/make_icons.py`). Keine Inline-Skripte oder -Styles (CSP); JavaScript als Datei unter `static/js/`.
  Keine externen CDNs oder Schriften.
- **Barrierefreiheit:** WCAG AA; neue Seiten in `e2e/pages.spec.ts` mit axe prüfen.
- **Tests:** pytest für Fachlogik und Rechte (`portal/<app>/tests/`), E2E für wichtige Abläufe.
- **Datenbank:** SQLite; Änderungen nur über Django-Migrationen. Lange Schreibtransaktionen vermeiden.
- **Konfiguration** nur über `PORTAL_*`-Umgebungsvariablen (`portal/settings.py`, `docs/betrieb.md`).
- **Abhängigkeiten:** Python in `pyproject.toml`/`uv.lock`, Frontend-Bibliotheken in `package.json`
  (kopiert von `scripts/vendor.mjs`). Renovate hält alles aktuell.
- **Produktion:** Stack im Repo `tlandsberger/homecloud` (`application/judo-portal/`). Neue Umgebungsvariablen dort
  nachziehen.
