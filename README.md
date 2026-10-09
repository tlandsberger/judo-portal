# judo-portal

Portal für Mitglieder und Funktionäre unseres Judo-Vereins. Login-geschützt,
verfügbar als Web-App sowie als Android- und iOS-App.

Initiale Features:

- Mitglieder- und Benutzerverwaltung
- Events: Trainings und Veranstaltungen
- Übungsleiterabrechnung

## Technologie auf einen Blick

| Bereich | Technologie |
|---|---|
| Clients (Web, Android, iOS) | Kotlin Multiplatform + Compose Multiplatform |
| Backend | Spring Boot (Kotlin), modularer Monolith mit Spring Modulith, Java 25 LTS |
| Datenbank | PostgreSQL + Flyway |
| Login | Keycloak (OIDC) |
| Betrieb | Docker Compose (Caddy, Backend, Keycloak, PostgreSQL) |

Details in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), Entscheidungen in [`docs/adr/`](docs/adr/).

## Entwickeln

Voraussetzungen: JDK 25 (Gradle lädt es bei Bedarf automatisch), Podman (oder Docker) für
Datenbank und Keycloak, Android SDK für die Android-App, macOS + Xcode für iOS.

```bash
podman compose -f infra/compose.dev.yaml up -d       # Postgres + Keycloak starten (infra/README.md)
./gradlew build                                      # alles bauen, testen, Code-Stil prüfen
./gradlew spotlessApply                              # Code formatieren
./gradlew :backend:bootRun                           # Backend starten (Port 8080)
./gradlew :client:androidApp:installDebug            # Android-App auf Gerät/Emulator
./gradlew :client:composeApp:wasmJsBrowserDevelopmentRun   # Web-App im Browser
```

## Status

Schritt 3 von 9: Repo-Skelett (Module, Build, CI) und lokale Infrastruktur (PostgreSQL, Keycloak
mit Testnutzern) stehen. Fachliche Funktionen gibt es noch
keine. Die Roadmap steht in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#9-roadmap).
