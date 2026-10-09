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

## Status

Phase 1: Architektur ist festgelegt, Code gibt es noch keinen. Die Roadmap steht in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#9-roadmap).
