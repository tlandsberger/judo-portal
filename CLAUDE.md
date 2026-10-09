# CLAUDE.md – judo-portal

Vereinsportal „WTSV Judo“: Spring-Boot-Backend + Kotlin-Multiplatform-Clients (Android, iOS, Web).
Architektur: `docs/ARCHITECTURE.md`, Entscheidungen: `docs/adr/`.

## Befehle

```bash
./gradlew build              # Build, Tests, Spotless/ktlint-Check (alle Module)
./gradlew spotlessApply      # Formatierung korrigieren – vor jedem Commit
./gradlew :backend:test      # Backend-Tests inkl. Spring-Modulith-Verifikation
./gradlew :shared-api:jvmTest
./gradlew :client:androidApp:assembleDebug
./gradlew :client:composeApp:wasmJsBrowserDistribution
./gradlew :client:composeApp:linkDebugFrameworkIosSimulatorArm64   # nur macOS
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
| `shared-api` | `de.landsberger.judo.portal.api` | DTOs für Backend und Clients (KMP: jvm, ios, wasmJs) |
| `client/shared` | `de.landsberger.judo.portal.client` | API-Client, später Auth und ViewModels |
| `client/composeApp` | `de.landsberger.judo.portal.ui` | Compose-Multiplatform-UI |
| `client/androidApp` | `de.landsberger.judo.portal` | Android-App-Modul (AGP 9) |

## Regeln

- **Backend-Module** (`members`, `events`, `billing`, `shared`) sind direkte Unterpakete von
  `...portal.backend`. Andere Module nur über deren Package-Root oder Domain-Events ansprechen,
  nie über `internal`-Unterpakete. `ModularityTest` erzwingt das.
- **Rollen** (`member`, `trainer`, `board`, `treasurer`, `admin`) sind fest, siehe ADR 0003.
  Fachliche Autorisierung gehört ins Backend.
- **API-Verträge** liegen in `shared-api`, keine DTO-Duplikate in Backend oder Client.
  `shared-api` und Android kompilieren auf Java-21-Bytecode, nur das Backend auf Java 25.
- **API:** Endpunkte unter `/api/**`. Request- und Response-Typen nur aus `shared-api`
  (`@Serializable`, JSON über kotlinx.serialization, ADR 0006). Controller erhalten den Nutzer als
  `CurrentUser`-Parameter (`backend.shared`), nie als `Jwt`. Rollen prüfen mit
  `@PreAuthorize("hasRole('TRAINER')")` o. Ä.
- **Tests:** Controller per `@WebMvcTest` + `jwt()` (siehe `MeControllerTest`), Ende-zu-Ende mit
  Testcontainers (siehe `ApiSecurityIT`, braucht Docker oder Podman-Socket).
- **Versionen** nur in `gradle/libs.versions.toml`. Container-Images in `infra/compose.dev.yaml`
  und `ApiSecurityIT` synchron halten.
- **Datenbank**-Änderungen nur über neue Flyway-Migrationen (`backend/src/main/resources/db/migration`,
  `V<n>__beschreibung.sql`). Bestehende Migrationen nie ändern, Hibernate nur `validate`.
- **Sprache:** Doku und Kommentare auf Deutsch, Code-Bezeichner auf Englisch.
- **Neue Architekturentscheidungen** bekommen ein ADR in `docs/adr/`.
