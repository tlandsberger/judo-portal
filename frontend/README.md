# Frontend – WTSV Judo (Angular-PWA)

Progressive Web App des Vereinsportals: Angular 22, Angular Material (M3, Vereinsfarbe `#027d31`),
Login per Keycloak (Authorization Code + PKCE). Architektur: [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md),
Entscheidung: [ADR 0007](../docs/adr/0007-pwa-mit-angular-und-openapi.md).

## Voraussetzungen

- Node.js 24 (siehe `../.nvmrc`, z. B. `nvm use`)
- Laufende Infrastruktur (`podman compose -f infra/compose.dev.yaml up -d`) und Backend (`./gradlew :backend:bootRun`)

## Befehle

```bash
npm ci                 # Abhängigkeiten installieren
npm start              # Dev-Server auf http://localhost:4200 (Proxy /api → :8080)
npm test -- --watch=false   # Unit-Tests (Vitest)
npm run lint           # ESLint
npm run format         # Prettier
npm run build          # Production-Build inkl. Service Worker → dist/frontend
npm run generate:api   # TypeScript-Typen aus ../api/openapi.json erzeugen
npx playwright test    # E2E gegen echte Infra + Backend (startet den Dev-Server selbst)
python3 scripts/generate-icons.py   # Favicon/PWA-Icons aus public/branding/logo-signet.png
```

Testnutzer (Passwort `test`): `mitglied@`, `trainer@`, `abteilungsleiter@`, `admin@test.local`.

## Aufbau

| Pfad                             | Inhalt                                                                      |
| -------------------------------- | --------------------------------------------------------------------------- |
| `src/app/api/`                   | `schema.d.ts` (generiert, nicht bearbeiten) und `api-types.ts` (Typ-Aliase) |
| `src/app/auth/`                  | OIDC-Konfiguration und Route-Guards                                         |
| `src/app/pages/`                 | Seiten (lazy geladen): `start`, `home`                                      |
| `src/app/shared/`                | Kleine Helfer, z. B. deutsche Rollenbezeichnungen                           |
| `src/styles.scss`, `src/styles/` | Theme (M3-Palette aus `#027d31`)                                            |
| `public/`                        | Manifest, Icons, Logos (`branding/`)                                        |
| `e2e/`                           | Playwright-Tests inkl. AXE-Barrierefreiheitsprüfung                         |

## Hinweise

- **API-Änderungen:** Erst im Backend `api/openapi.json` neu schreiben (`./gradlew :backend:test -Popenapi.update`),
  dann `npm run generate:api`. Die CI prüft beide Schritte.
- **Tokens** liegen im `sessionStorage` (nur dieses Fenster), nie im `localStorage`.
- **Farben** nur über Material-System-Tokens (`var(--mat-sys-…)`), damit das spätere Dark-Theme ohne
  Komponentenänderungen funktioniert.
- **Schriften** werden lokal ausgeliefert (`@fontsource/roboto`), keine Google-Fonts-Aufrufe (DSGVO).
- Der Service Worker ist nur im Production-Build aktiv und cacht keine `/api`-Antworten.
