# Deployment: Container-Images

Das Portal besteht im Betrieb aus vier Containern. Zwei Images bauen wir selbst ([ADR 0010](adr/0010-container-images-und-registry.md)),
Keycloak und PostgreSQL sind offizielle Images.

```
Internet ──HTTPS──▶ Reverse Proxy der Homecloud ──HTTP──▶ web:8080 (Caddy + PWA)
                                                           ├── /api/*  ──▶ backend:8080
                                                           └── /auth/* ──▶ keycloak:8080
                                                   backend ──▶ postgres:5432, keycloak (Admin-API)
```

> Die fertige Produktions-Compose (Keycloak-Prod-Realm, Backup, Mailserver) kommt mit Schritt 9.
> Diese Seite beschreibt die Images und was sie erwarten.

## Images und Tags

| Image | Inhalt |
|---|---|
| `ghcr.io/tlandsberger/judo-portal-backend` | Spring-Boot-Backend, Port 8080 |
| `ghcr.io/tlandsberger/judo-portal-web` | PWA mit Caddy, Port 8080 (nur HTTP) |

Beide Images gibt es nur für `linux/amd64`. Sie laufen als Nicht-root-Nutzer (UID 10001).

| Tag | Wann |
|---|---|
| `sha-<commit>` | bei jedem Push, nach grüner CI |
| `<branch>` (z. B. `claude-gracious-volta-fspxmq`) | letzter grüner Stand des Branches |
| `latest` | letzter grüner Stand des Default-Branches |
| `1.2.3`, `1.2` | bei einem Git-Tag `v1.2.3` |

Produktiv immer einen festen Tag verwenden (`sha-…` oder eine Version), damit klar ist, was läuft und ein
Zurückrollen einfach bleibt.

### Einmalig nach dem ersten Push: Pakete öffentlich machen

Neue Pakete in GHCR sind zunächst privat. Für beide Pakete einmal:
GitHub → Profil → **Packages** → `judo-portal-backend` bzw. `judo-portal-web` → **Package settings** →
**Change visibility** → **Public**. Danach klappt `docker pull` ohne Login.

## Umgebungsvariablen

### Backend (`judo-portal-backend`)

| Variable | Beispiel | Bedeutung |
|---|---|---|
| `PORTAL_DB_URL` | `jdbc:postgresql://postgres:5432/portal` | Datenbank des Portals |
| `PORTAL_DB_USER` | `portal` | |
| `PORTAL_DB_PASSWORD` | – | |
| `PORTAL_ISSUER_URI` | `https://judo.example.org/auth/realms/judo` | Issuer der Tokens, genau so wie im Token (`iss`) |
| `PORTAL_KEYCLOAK_URL` | `http://keycloak:8080/auth` | Keycloak für die Admin-API (Einladungen, ADR 0009), intern |
| `PORTAL_KEYCLOAK_CLIENT_SECRET` | – | Secret des Clients `judo-portal-backend` |
| `PORTAL_PUBLIC_URL` | `https://judo.example.org` | Adresse der PWA (Ziel nach dem Einladungslink) |
| `SPRINGDOC_SWAGGER_UI_ENABLED`, `SPRINGDOC_API_DOCS_ENABLED` | `false` | Swagger-UI und API-Beschreibung in Produktion abschalten |
| `JAVA_TOOL_OPTIONS` | `-Xss512k` | optionale JVM-Optionen; der Heap ist auf 75 % des Container-Speichers begrenzt |

Health-Check: `GET /actuator/health` auf Port 8080 (nur intern, wird von Caddy nicht weitergeleitet).
Flyway migriert die Datenbank beim Start.

> **Hinweis zum Issuer:** Das Backend lädt beim ersten Token die Schlüssel über `PORTAL_ISSUER_URI`, also über die
> öffentliche Adresse. Der Backend-Container muss die Domain daher erreichen können (Hairpin-NAT bzw. DNS in der
> Homecloud). Ob wir das intern abkürzen, klären wir in Schritt 9.

### Web (`judo-portal-web`)

| Variable | Standard | Bedeutung |
|---|---|---|
| `BACKEND_URL` | `backend:8080` | Ziel für `/api/*` |
| `KEYCLOAK_URL` | `keycloak:8080` | Ziel für `/auth/*` |
| `TRUSTED_PROXIES` | `private_ranges` | Netze, deren `X-Forwarded-*`-Header übernommen werden |

Keycloak muss dafür unter dem Pfad `/auth` laufen und den Proxy-Headern vertrauen:
`KC_HTTP_RELATIVE_PATH=/auth`, `KC_HOSTNAME=https://judo.example.org/auth`, `KC_PROXY_HEADERS=xforwarded`.

## Anforderungen an den Reverse Proxy der Homecloud

- Eine Domain (z. B. `judo.example.org`) mit TLS, komplett weitergeleitet auf `web:8080`.
- `X-Forwarded-Proto` und `X-Forwarded-Host` setzen (Standard bei Traefik, Nginx Proxy Manager, Caddy).
- Request-Größe mindestens 2 MB (CSV-Import).
- Der Proxy muss aus einem privaten Netz kommen (Docker-Netz, LAN), sonst ignorieren Caddy und Tomcat die
  `X-Forwarded-*`-Header. Andernfalls `TRUSTED_PROXIES` setzen.

## Was der Web-Container regelt

- **PWA:** Deep Links (z. B. `/members/…`) liefern `index.html`; fehlende Dateien liefern 404.
- **Caching:** `index.html`, `ngsw.json`, Service Worker, Manifest und Icons mit `no-cache`, damit Updates
  ankommen; Dateien mit Hash im Namen ein Jahr `immutable`.
- **Sicherheits-Header:** Content-Security-Policy (nur eigene Quellen), `X-Frame-Options: DENY`,
  `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`.

## Lokal bauen und prüfen

```bash
docker build -f backend/Dockerfile -t judo-portal-backend:local .
docker build -t judo-portal-web:local frontend

podman compose -f infra/compose.dev.yaml up -d         # Dev-Infrastruktur
infra/scripts/image-smoke-test.sh                      # startet beide Images und prüft sie
```

Die CI macht dasselbe im Job „Container-Images“ und pusht erst, wenn der Smoke-Test grün ist.
