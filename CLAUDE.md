# CLAUDE.md – judo-portal

Vereinsportal „WTSV Judo“: Spring-Boot-Backend (Kotlin) + Angular-PWA in `frontend/`
(eigene Regeln in `frontend/CLAUDE.md`, Befehle in `frontend/README.md`).
Architektur: `docs/ARCHITECTURE.md`, Entscheidungen: `docs/adr/`.

## Befehle

```bash
./gradlew build              # Build, Tests, Spotless/ktlint-Check (alle Module)
./gradlew spotlessApply      # Formatierung korrigieren – vor jedem Commit
./gradlew :backend:test      # Backend-Tests inkl. Spring-Modulith-Verifikation
./gradlew :backend:test -Popenapi.update   # API-Vertrag api/openapi.json nach API-Änderungen neu schreiben
```

Lokale Infrastruktur (Postgres :5432, Keycloak :8081, Testnutzer `<rolle>@test.local` / `test`):

```bash
podman compose -f infra/compose.dev.yaml up -d   # bzw. docker compose
infra/scripts/smoke-test.sh                      # Tokens + Rollen aller Testnutzer prüfen
```

Realm-Änderungen nur in `infra/keycloak/realm-judo-dev.json` (Import nur beim ersten Start → `down -v`).
Test-Tokens per Password-Grant über den Client `judo-dev-tools` (siehe `infra/README.md`).

## Module

| Modul | Package | Zweck |
|---|---|---|
| `backend` | `de.landsberger.judo.portal.backend` | Spring Boot, Java 25 |
| `api/openapi.json` | – | API-Vertrag, aus dem Backend erzeugt (ADR 0007) |
| `frontend` | – | Angular-PWA (Node 24, `npm`), Typen aus `api/openapi.json` via `npm run generate:api` |

## Regeln

- **Backend-Module** (`members`, `events`, `billing`, `shared`) sind direkte Unterpakete von
  `...portal.backend`. Andere Module nur über deren Package-Root oder Domain-Events ansprechen,
  nie über `internal`-Unterpakete. `ModularityTest` erzwingt das.
- **Rollen** (`member`, `trainer`, `department_head`, `admin`) sind fest, siehe ADR 0008.
  Fachliche Autorisierung gehört ins Backend.
- **API-Vertrag** ist `api/openapi.json` (springdoc, ADR 0007). Nach jeder API-Änderung neu schreiben
  (`-Popenapi.update`) und den Diff mit committen, sonst schlägt `OpenApiContractIT` fehl.
  Nicht-nullbare Kotlin-Felder werden automatisch `required`.
- **Fehler** als Problem Details: fachliche Fehler über `NotFoundException`, `ConflictException`,
  `InvalidInputException` (`backend.shared`), Feldfehler stehen in `errors: [{field, message}]` mit deutschen Texten
  (`ApiExceptionHandler`). Bean-Validation-Meldungen immer explizit auf Deutsch setzen.
- **API:** Endpunkte unter `/api/**`, DTOs als Kotlin-Data-Classes im jeweiligen Modul (`internal/web`),
  JSON über Jackson. Enums im JSON kleingeschrieben (`@JsonValue`, siehe `Role`). Controller erhalten den Nutzer als
  `CurrentUser`-Parameter (`backend.shared`), nie als `Jwt`. Rollen prüfen mit
  `@PreAuthorize("hasRole('TRAINER')")` o. Ä.
- **Tests:** Controller per `@WebMvcTest` + `jwt()` (siehe `MeControllerTest`), Ende-zu-Ende mit
  Testcontainers (Basis `IntegrationTestBase`, z. B. `ApiSecurityIT`, braucht Docker oder Podman-Socket).
- **Versionen** nur in `gradle/libs.versions.toml`. Container-Images in `infra/compose.dev.yaml`
  und `IntegrationTestBase` synchron halten.
- **Datenbank**-Änderungen nur über neue Flyway-Migrationen (`backend/src/main/resources/db/migration`,
  `V<n>__beschreibung.sql`). Bestehende Migrationen nie ändern, Hibernate nur `validate`.
- **API-Änderung = drei Schritte:** Backend ändern → `-Popenapi.update` → im Frontend `npm run generate:api`.
  Die CI prüft `api/openapi.json` und `schema.d.ts`.
- **Frontend:** Texte nur auf Deutsch (kein i18n), Farben nur über `var(--mat-sys-…)`. Tokens nie im
  `localStorage`, keine externen Fonts oder CDNs (DSGVO). Neue Seiten mit Unit-Tests, wichtige Abläufe in
  `frontend/e2e/` mit AXE-Check. Formulare mit Signal Forms; Feature-Bereiche als nachgeladene Routen
  (`loadChildren`) mit `provideFormDefaults()`. Rechte für die Anzeige nur in `auth/permissions.ts`
  (spiegelt die `@PreAuthorize`-Regeln), Seiten schützt `permissionGuard`.
- **Sprache:** Doku und Kommentare auf Deutsch, Code-Bezeichner auf Englisch.
- **Neue Architekturentscheidungen** bekommen ein ADR in `docs/adr/`.
