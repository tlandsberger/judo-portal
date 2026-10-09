# Lokale Entwicklungsumgebung

PostgreSQL und Keycloak (Realm `judo` mit Rollen, Clients und Testnutzern) per Compose.
Die Datei funktioniert mit **Podman** und mit Docker.

## Starten & Stoppen

Voraussetzung: Podman mit Compose-Provider (`podman-compose` oder `docker-compose`).

```bash
podman compose -f infra/compose.dev.yaml up -d      # starten
infra/scripts/smoke-test.sh                         # prüfen (braucht curl + jq)
podman compose -f infra/compose.dev.yaml logs -f keycloak
podman compose -f infra/compose.dev.yaml down       # stoppen, Daten bleiben
podman compose -f infra/compose.dev.yaml down -v    # stoppen und alles zurücksetzen
```

## Dienste

| Dienst | Adresse | Zugang |
|---|---|---|
| Keycloak-Admin-Konsole | http://localhost:8081/admin | `admin` / `admin` |
| Realm `judo` (Issuer) | http://localhost:8081/realms/judo | – |
| Account-Seite (Login testen) | http://localhost:8081/realms/judo/account | Testnutzer, siehe unten |
| PostgreSQL | `localhost:5432` | DB `portal`, Nutzer `portal` / `portal` (Backend) |

Die Passwörter sind reine Dev-Defaults. Sie lassen sich über Umgebungsvariablen überschreiben:
`POSTGRES_PASSWORD`, `PORTAL_DB_PASSWORD`, `KEYCLOAK_DB_PASSWORD`, `KEYCLOAK_ADMIN_USER` und
`KEYCLOAK_ADMIN_PASSWORD`.

## Testnutzer

Passwort jeweils `test`.

| Nutzer | Rollen |
|---|---|
| `mitglied@test.local` | member |
| `trainer@test.local` | member, trainer |
| `vorstand@test.local` | member, board |
| `kasse@test.local` | member, treasurer |
| `admin@test.local` | admin |

## Clients im Realm

| Client | Zweck |
|---|---|
| `judo-portal-app` | Apps (Android, iOS, Web): Authorization Code + PKCE, public |
| `judo-dev-tools` | **Nur Dev:** Password-Grant für Tokens per `curl` |

Ein Token für API-Tests holen:

```bash
curl -s http://localhost:8081/realms/judo/protocol/openid-connect/token \
  -d grant_type=password -d client_id=judo-dev-tools \
  -d username=trainer@test.local -d password=test | jq -r .access_token
```

## Realm ändern

Die Konfiguration steht in `keycloak/realm-judo-dev.json` und wird nur beim **ersten** Start
importiert. Wenn der Realm schon existiert, ignoriert Keycloak die Datei. Für Änderungen:

1. die JSON-Datei anpassen,
2. `down -v` und `up -d` ausführen, damit der Realm neu importiert wird.

Änderungen, die du in der Admin-Konsole machst, gehen dabei verloren, wenn sie nicht in der
JSON-Datei stehen. Der Produktiv-Realm bekommt später eine eigene Datei ohne Testnutzer und ohne
`judo-dev-tools`.

## Hinweise zu Podman

- Die Bind-Mounts sind mit `:Z` markiert, damit sie auch unter SELinux (Fedora, RHEL) lesbar sind.
- Kurz-Imagenamen (`postgres`, `keycloak/keycloak`) löst Podman über die Short-Name-Aliase oder
  `unqualified-search-registries` in `/etc/containers/registries.conf` auf. Fragt Podman nach
  der Registry, `docker.io` wählen.
