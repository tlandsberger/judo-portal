# judo-portal

Portal für Mitglieder und Funktionäre unseres Judo-Vereins. Login-geschützt,
als Progressive Web App (PWA) im Browser und auf Android/iOS installierbar.

Initiale Features:

- Mitglieder- und Benutzerverwaltung
- Events: Trainings und Veranstaltungen
- Übungsleiterabrechnung

## Technologie auf einen Blick

| Bereich | Technologie |
|---|---|
| Frontend (PWA) | Angular 22 + Angular Material, Login per PKCE ([`frontend/`](frontend/README.md)) |
| API-Vertrag | OpenAPI (`api/openapi.json`, Swagger-UI unter `/swagger-ui.html`) |
| Backend | Spring Boot (Kotlin), modularer Monolith mit Spring Modulith, Java 25 LTS |
| Datenbank | PostgreSQL + Flyway |
| Login | Keycloak (OIDC) |
| Betrieb | Docker Compose; Images `ghcr.io/tlandsberger/judo-portal-backend` und `…-web` ([`docs/deployment.md`](docs/deployment.md)) |

Details in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), Entscheidungen in [`docs/adr/`](docs/adr/).

## Entwickeln

Voraussetzungen: JDK 25 (Gradle lädt es bei Bedarf automatisch), Podman (oder Docker) für
Datenbank und Keycloak, Node.js 24 für das Frontend (`.nvmrc`).

```bash
podman compose -f infra/compose.dev.yaml up -d       # Postgres + Keycloak starten (infra/README.md)
./gradlew build                                      # alles bauen, testen, Code-Stil prüfen
./gradlew spotlessApply                              # Code formatieren
./gradlew :backend:bootRun                           # Backend starten (Port 8080, braucht die Infra)
./gradlew :backend:test -Popenapi.update            # API-Vertrag api/openapi.json neu schreiben
cd frontend && npm ci && npm start                   # PWA auf http://localhost:4200 (Login: trainer@test.local / test)
```

Backend ausprobieren (Infra und Backend laufen):

```bash
TOKEN=$(curl -s http://localhost:8081/realms/judo/protocol/openid-connect/token \
  -d grant_type=password -d client_id=judo-dev-tools \
  -d username=trainer@test.local -d password=test | jq -r .access_token)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/me
# {"subject":"…","displayName":"Tom Trainer","email":"trainer@test.local","roles":["member","trainer"]}
```

## Status

Mitgliederverwaltung mit CSV-Import und Zugängen für Mitglieder und Eltern ist fertig (Schritte 6a–6c).
Die CI baut daraus die Container-Images und legt sie in GHCR ab (Schritt 6d, [`docs/deployment.md`](docs/deployment.md)).
Als Nächstes folgen Events und die Übungsleiterabrechnung. Die Roadmap steht in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#9-roadmap).
