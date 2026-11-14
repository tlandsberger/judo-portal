# 0006 – Automatisierte Wartung und wöchentliche Releases

- Status: angenommen
- Datum: 2026-11-14

## Entscheidung

- **Conventional Commits** für alle Commits (CI prüft).
- **CI** bei jedem Push: ruff, mypy, Migrationen, pytest; Image bauen, Smoke-Test, E2E gegen das Image im offiziellen
  Playwright-Container (axe-Barrierefreiheit, Screenshot-Vergleich hell/dunkel auf Desktop und Handy).
- **Renovate**: Patch/Minor automatisch mergen, wenn die CI grün ist; Major mit Freigabe. Playwright-Paket und
  -Container werden gemeinsam aktualisiert (Screenshots hängen an der Version).
- **Release jeden Sonntag 23:00 (Berlin)**, wenn `main` neue Commits hat: git-cliff ermittelt die Version
  (`fix` Patch, `feat` Minor, Breaking Major), erstellt Tag und GitHub-Release mit Changelog; das Image wird als
  `X.Y.Z`, `X.Y` und `latest` nach `ghcr.io/tlandsberger/judo-portal` gepusht. Manuell startbar.
- **Live-Check** täglich gegen die Produktivseite (`LIVE_URL`).

## Konsequenzen

- ➕ Updates, Tests und Deployments laufen ohne Handarbeit; Fehler fallen vor dem Release auf.
- ➖ Screenshot-Tests brauchen nach gewollten Design-Änderungen neue Referenzbilder.
