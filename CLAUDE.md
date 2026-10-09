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
- **Versionen** nur in `gradle/libs.versions.toml`.
- **Datenbank**-Änderungen nur über Flyway-Migrationen (ab Schritt 4).
- **Sprache:** Doku und Kommentare auf Deutsch, Code-Bezeichner auf Englisch.
- **Neue Architekturentscheidungen** bekommen ein ADR in `docs/adr/`.
