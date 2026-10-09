# Architecture Decision Records

Jede wichtige Architekturentscheidung bekommt ein kurzes ADR mit Kontext, Entscheidung,
Konsequenzen und verworfenen Alternativen. ADRs werden nicht nachträglich umgeschrieben. Eine
geänderte Entscheidung bekommt ein neues ADR, das das alte als „ersetzt“ markiert.

| Nr. | Titel | Status |
|---|---|---|
| [0001](0001-kotlin-multiplatform-clients.md) | Kotlin Multiplatform + Compose Multiplatform für alle Clients | angenommen |
| [0002](0002-spring-boot-kotlin-backend.md) | Spring Boot mit Kotlin und Java 25 LTS als Backend | angenommen |
| [0003](0003-keycloak-identity.md) | Keycloak als Identity Provider, feste Rollen | angenommen |
| [0004](0004-modularer-monolith.md) | Modularer Monolith mit Spring Modulith | angenommen |
| [0005](0005-hosting-container-homecloud.md) | Betrieb per Docker Compose in der Homecloud | angenommen |
| [0006](0006-api-vertrag-und-token-pruefung.md) | API-Vertrag (kotlinx.serialization) & Token-Prüfung (Audience) | angenommen |

Vorlage für neue ADRs:

```markdown
# NNNN – Titel

- Status: vorgeschlagen | angenommen | ersetzt durch NNNN
- Datum: JJJJ-MM-TT

## Kontext
## Entscheidung
## Konsequenzen
## Verworfene Alternativen
```
