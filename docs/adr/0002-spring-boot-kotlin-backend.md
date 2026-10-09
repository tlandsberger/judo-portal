# 0002 – Spring Boot mit Kotlin und Java 25 LTS als Backend

- Status: angenommen
- Datum: 2026-10-09

## Kontext

Das Backend enthält die fachliche Logik (Mitglieder, Events, Abrechnung mit Freigabe-Workflow)
und muss rollenbasierte Autorisierung, Audit und Dokumentenerzeugung (PDF) unterstützen.
Es soll langfristig wartbar sein und zum Kotlin-Stack der Clients passen ([0001](0001-kotlin-multiplatform-clients.md)).

## Entscheidung

- **Spring Boot** in **Kotlin** mit Spring Web MVC, Spring Security (OAuth2 Resource Server),
  Spring Data JPA, Bean Validation und springdoc-openapi.
- **Java 25 LTS** (aktuellste LTS-Version) als Gradle-Toolchain und Laufzeit
  (`eclipse-temurin:25-jre`).
- **PostgreSQL** als Datenbank, Schemaänderungen ausschließlich über **Flyway**-Migrationen.
- REST/JSON-API unter `/api`, Request/Response-DTOs aus dem KMP-Modul `shared-api`.
- Tests mit JUnit 5 und Testcontainers gegen eine echte PostgreSQL-Datenbank.

## Konsequenzen

- ➕ Sehr verbreiteter, gut dokumentierter Stack, auch für spätere Helfer gut zugänglich.
- ➕ Spring Security bindet Keycloak als OIDC Resource Server ohne Eigenbau an.
- ➕ Virtuelle Threads (Java 21+) machen klassisches blockierendes MVC skalierbar genug, wir
  brauchen keinen reaktiven Stack.
- ➖ Höherer Speicherbedarf als z. B. Ktor. Für die Homecloud (eine Instanz, < 300 Nutzer) ist
  das unkritisch.
- Beim Repo-Setup ist zu prüfen, dass die eingesetzten Versionen von Spring Boot, Kotlin
  und Gradle Java 25 als Toolchain und Bytecode-Ziel vollständig unterstützen.

## Verworfene Alternativen

- **Ktor (Server):** schlanker und ebenfalls Kotlin, aber Security, Validierung, Persistenz und
  Modularisierung müssten selbst zusammengestellt werden.
- **Quarkus/Micronaut:** schneller Start und geringer Speicherbedarf, aber kleineres Ökosystem.
  Der Vorteil zählt bei einer dauerhaft laufenden Einzelinstanz kaum.
- **Managed BaaS (Supabase/Firebase):** wenig Betrieb, aber die fachliche Logik (Abrechnung,
  Freigaben) wäre über Funktionen und DB-Policies verstreut, und es entstünde eine Anbieterbindung.
