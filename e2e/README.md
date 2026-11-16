# E2E-Tests

Die Tests laufen gegen einen echten Portal-Container und im offiziellen Playwright-Container, damit die
Screenshot-Vergleiche lokal und in der CI identisch sind.

```bash
docker build -t judo-portal:local .
mkdir -p /tmp/portal-data && chmod 777 /tmp/portal-data
docker run -d --name portal-e2e -p 8000:8000 -v /tmp/portal-data:/data \
  -e PORTAL_SECRET_KEY=test -e PORTAL_BASE_URL=http://localhost:8000 -e PORTAL_SECURE_COOKIES=false \
  -e PORTAL_WEBAUTHN_ALLOW_INSECURE_ORIGIN=true -e PORTAL_EMAIL_FILE_PATH=/data/mails \
  -e PORTAL_INITIAL_ADMIN_EMAIL=admin@test.local judo-portal:local
npm ci
docker run --rm --network host -v "$PWD":/work -v /tmp/portal-data/mails:/mails -w /work -e MAIL_DIR=/mails \
  mcr.microsoft.com/playwright:v1.65.1-noble npx playwright test
```

- Jeder Lauf braucht einen frischen Container (der erste Administrator nimmt seine Einladung an).
- Mails liest der Test aus dem Verzeichnis des filebased-Mail-Backends (`MAIL_DIR`).
- Passkeys testet ein virtueller Authenticator von Chromium.
- **Referenzbilder neu erzeugen** (nach gewollten Design-Änderungen): denselben Befehl mit `--update-snapshots`
  und die geänderten Dateien unter `e2e/__screenshots__/` committen. Die Version des Playwright-Images muss zur
  Version von `@playwright/test` in `package.json` passen.
- **Screenshots der Hilfe** (ADR 0016): `e2e/hilfe.spec.ts` läuft als Projekt `hilfe` nach allen anderen Tests. Mit
  `-e HELP_SCREENSHOTS=1` im obigen `docker run` und `npx playwright test --project=hilfe` (bzw.
  `npm run help:screenshots`) landen die Bilder in `portal/help/static/help/img/`; die geänderten Dateien committen.
