# Deployment

Das Portal besteht im Betrieb aus Web, Backend, Keycloak und PostgreSQL. Zwei Images bauen wir selbst
([ADR 0010](adr/0010-container-images-und-registry.md)), Keycloak und PostgreSQL sind offizielle Images.

```
Internet ──HTTPS──▶ Reverse Proxy der Homecloud ──HTTP──▶ web:8080 (Caddy + PWA)
                                                           ├── /api/*  ──▶ backend:8080
                                                           └── /auth/* ──▶ keycloak:8080   (ohne /auth/admin, Master-Realm)
Admin ──HTTPS──▶ Reverse Proxy (geschützt) ───────────────────────────────▶ keycloak:8080   (Admin-Konsole)
                                                   backend ──▶ postgres:5432, keycloak (JWKS, Admin-API)
```

## Produktion: Homecloud

Das Portal läuft unter **https://judo.tlandsberger.de**. Die Compose-Datei liegt im Homecloud-Repo
(`tlandsberger/homecloud`, `application/judo-portal/docker-compose.yml`), Portainer deployt sie per GitOps.
Dort steht auch, welche Variablen in Portainer gesetzt werden.

| Adresse | Ziel | Zugang |
|---|---|---|
| `https://judo.tlandsberger.de` | `judo_web` (PWA, `/api`, `/auth`) | öffentlich (Cloudflare-Access-Bypass), Login über Keycloak |
| `https://judo-admin.tlandsberger.de` | `judo_keycloak` (Admin-Konsole) | nur hinter Cloudflare-Access-OTP |

Wichtige Punkte der Konfiguration:

- Keycloak läuft unter `/auth` mit `KC_HOSTNAME=https://judo.tlandsberger.de/auth` und
  `KC_HOSTNAME_ADMIN=https://judo-admin.tlandsberger.de/auth`. Die Web-App sperrt `/auth/admin` und den Master-Realm.
- Das Backend prüft den Issuer `https://judo.tlandsberger.de/auth/realms/judo`, lädt die Schlüssel aber intern
  (`SPRING_SECURITY_OAUTH2_RESOURCESERVER_JWT_JWK_SET_URI=http://keycloak:8080/auth/realms/judo/protocol/openid-connect/certs`).
- Interne Hostnamen ohne Unterstrich (`keycloak`, `backend` als Netzwerk-Aliase): Javas HTTP-Client lehnt Hosts wie
  `judo_keycloak` ab.
- `judo_db_dump` schreibt täglich um 02:00 `pg_dump`-Dateien beider Datenbanken, das restic-Backup der Homecloud
  sichert sie um 02:30 mit.

### Releases

1. Auf dem Default-Branch ein Git-Tag setzen: `git tag v1.2.0 && git push origin v1.2.0`.
2. Die CI baut und pusht die Images `1.2.0` und `1.2`.
3. Renovate öffnet im Homecloud-Repo einen PR für Backend und Web. Patch- und Minor-Versionen werden automatisch
   gemergt, Portainer deployt sie danach. Major-Versionen (`v2.0.0`) brauchen eine Freigabe im Dependency-Dashboard.

Datenbank-Migrationen laufen beim Start des Backends (Flyway). Ein Zurückrollen auf eine ältere Version geht nur,
wenn keine neue Migration dazugekommen ist, sonst aus dem Dump wiederherstellen.

### Realm einrichten (einmalig, Checkliste)

Keycloak startet leer. Den Realm `judo` richtest du einmal von Hand ein. Vorlage für alle Werte ist der Dev-Realm
`infra/keycloak/realm-judo-dev.json`.

**0. Master-Realm auf die Admin-Adresse stellen** (sonst lädt die Admin-Konsole nicht, weil die Web-App den
Master-Realm auf der Portal-Adresse sperrt). Einmal auf dem Host bzw. in der Portainer-Konsole des Containers:

```bash
docker exec judo_keycloak bash -c '/opt/keycloak/bin/kcadm.sh config credentials --server http://localhost:8080/auth \
  --realm master --user admin --password "$KC_BOOTSTRAP_ADMIN_PASSWORD" \
  && /opt/keycloak/bin/kcadm.sh update realms/master -s "attributes.frontendUrl=https://judo-admin.tlandsberger.de/auth"'
```

Danach https://judo-admin.tlandsberger.de öffnen und mit `admin` und `JUDO_KEYCLOAK_ADMIN_PASSWORD` anmelden.

**1. Dauerhaften Admin anlegen:** Im Realm `master` einen eigenen Benutzer mit der Rolle `admin` anlegen, damit
anmelden und den temporären Benutzer `admin` löschen (Keycloak weist oben darauf hin).

**2. Realm `judo` anlegen** (*Manage realms → Create realm*), dann unter *Realm settings*:

| Reiter | Einstellung |
|---|---|
| General | Display name `WTSV Judo` |
| Login | *User registration* aus, *Forgot password* an, *Remember me* an, *Login with email* an, *Duplicate emails* aus |
| Email | From `portal@tlandsberger.de`, Display name `WTSV Judo`; Host `smtp.ionos.de`, Port `587`, *Enable StartTLS* an, *Authentication* an, Benutzer/Passwort des IONOS-Postfachs → *Test connection* |
| Localization | *Internationalization* an, unterstützte Sprache nur `Deutsch`, Standard `Deutsch` |
| Security defenses → Brute force detection | *Lockout temporarily* |
| Sessions / Tokens | *Revoke Refresh Token* an, *Refresh Token Max Reuse* `0` |

Unter *Authentication → Policies → Password policy*: *Minimum length* `10`, *Not username*, *Not email*.

**3. Realm-Rollen** (*Realm roles → Create role*): `member`, `trainer`, `department_head`, `admin`.

**4. Client `judo-portal-app`** (die PWA, *Clients → Create client*):

- Client ID `judo-portal-app`, Name `WTSV Judo PWA`
- *Client authentication* aus, nur *Standard flow* an (kein *Direct access grants*)
- Valid redirect URIs `https://judo.tlandsberger.de/*`, Valid post logout redirect URIs `https://judo.tlandsberger.de/*`,
  Web origins `https://judo.tlandsberger.de`
- *Advanced → Proof Key for Code Exchange Code Challenge Method* `S256`
- *Client scopes → judo-portal-app-dedicated*:
  - *Add mapper → By configuration → Audience*: Name `audience-judo-portal-api`, *Included Custom Audience*
    `judo-portal-api`, *Add to access token* an, *Add to ID token* aus
  - Reiter *Scope*: *Full scope allowed* aus, dann die vier Realm-Rollen zuweisen

**5. Client `judo-portal-backend`** (Einladungen, ADR 0009):

- Client ID `judo-portal-backend`, Name `WTSV Judo Backend`
- *Client authentication* an, nur *Service accounts roles* an (kein Standard flow, keine Direct access grants)
- Reiter *Service accounts roles → Assign role → Client roles*: `realm-management` `manage-users`, `view-users`,
  `query-users`
- Reiter *Credentials*: Client secret kopieren und in Portainer als `JUDO_BACKEND_CLIENT_SECRET` eintragen,
  Stack neu deployen

**6. Eigenes Konto** im Realm `judo` (*Users → Add user*): E-Mail als Benutzername, *Email verified* an, Passwort
setzen (*Credentials*), Rollen `member`, `department_head` und `admin` zuweisen.

**7. Prüfen:** https://judo.tlandsberger.de öffnen, anmelden, *Mitglieder* aufrufen, sich selbst bzw. ein
Testmitglied einladen und prüfen, ob die Mail ankommt.

Spätere Änderungen am Realm macht ihr ebenfalls in der Admin-Konsole. Neue Einstellungen aus dem Dev-Realm
(`realm-judo-dev.json`) müssen in Produktion von Hand nachgezogen werden.

### Backup und Wiederherstellung

Die Dumps liegen im Volume `<Stack-Name>_judo_db_dumps` (`portal-JJJJ-MM-TT.dump`, `keycloak-JJJJ-MM-TT.dump`,
14 Tage). Sofort-Dump: `docker exec judo_db_dump sh /judo-db-dump.sh now`.

Wiederherstellen (Beispiel Portal-Datenbank, Backend vorher stoppen):

```bash
docker stop judo_backend
docker exec judo_db_dump sh -c 'PGPASSWORD="$JUDO_DB_PASSWORD" \
  pg_restore -h judo_db -U portal -d portal --clean --if-exists /dumps/portal-2026-11-03.dump'
docker start judo_backend
```

## Container-Images

### Images und Tags

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

#### Einmalig nach dem ersten Push: Pakete öffentlich machen

Neue Pakete in GHCR sind zunächst privat. Für beide Pakete einmal:
GitHub → Profil → **Packages** → `judo-portal-backend` bzw. `judo-portal-web` → **Package settings** →
**Change visibility** → **Public**. Danach klappt `docker pull` ohne Login.

### Umgebungsvariablen

#### Backend (`judo-portal-backend`)

| Variable | Beispiel | Bedeutung |
|---|---|---|
| `PORTAL_DB_URL` | `jdbc:postgresql://postgres:5432/portal` | Datenbank des Portals |
| `PORTAL_DB_USER` | `portal` | |
| `PORTAL_DB_PASSWORD` | – | |
| `PORTAL_ISSUER_URI` | `https://judo.example.org/auth/realms/judo` | Issuer der Tokens, genau so wie im Token (`iss`) |
| `SPRING_SECURITY_OAUTH2_RESOURCESERVER_JWT_JWK_SET_URI` | `http://keycloak:8080/auth/realms/judo/protocol/openid-connect/certs` | optional: Schlüssel intern laden statt über die öffentliche Adresse |
| `PORTAL_KEYCLOAK_URL` | `http://keycloak:8080/auth` | Keycloak für die Admin-API (Einladungen, ADR 0009), intern |
| `PORTAL_KEYCLOAK_CLIENT_SECRET` | – | Secret des Clients `judo-portal-backend` |
| `PORTAL_PUBLIC_URL` | `https://judo.example.org` | Adresse der PWA (Ziel nach dem Einladungslink) |
| `SPRINGDOC_SWAGGER_UI_ENABLED`, `SPRINGDOC_API_DOCS_ENABLED` | `false` | Swagger-UI und API-Beschreibung in Produktion abschalten |
| `JAVA_TOOL_OPTIONS` | `-Xss512k` | optionale JVM-Optionen; der Heap ist auf 75 % des Container-Speichers begrenzt |

Health-Check: `GET /actuator/health` auf Port 8080 (nur intern, wird von Caddy nicht weitergeleitet).
Flyway migriert die Datenbank beim Start.

> **Hinweis zum Issuer:** Ohne `…_JWK_SET_URI` lädt das Backend die Schlüssel über `PORTAL_ISSUER_URI`, also über
> die öffentliche Adresse. In der Homecloud ist deshalb die interne JWKS-Adresse gesetzt.

#### Web (`judo-portal-web`)

| Variable | Standard | Bedeutung |
|---|---|---|
| `BACKEND_URL` | `backend:8080` | Ziel für `/api/*` |
| `KEYCLOAK_URL` | `keycloak:8080` | Ziel für `/auth/*` |
| `TRUSTED_PROXIES` | `private_ranges` | Netze, deren `X-Forwarded-*`-Header übernommen werden |

Keycloak muss dafür unter dem Pfad `/auth` laufen und den Proxy-Headern vertrauen:
`KC_HTTP_RELATIVE_PATH=/auth`, `KC_HOSTNAME=https://judo.example.org/auth`, `KC_PROXY_HEADERS=xforwarded`.
`/auth/admin*` und `/auth/realms/master*` liefert die Web-App immer mit 404 aus, die Admin-Konsole braucht deshalb
eine eigene Adresse (`KC_HOSTNAME_ADMIN`).

### Anforderungen an den Reverse Proxy

- Eine Domain (z. B. `judo.example.org`) mit TLS, komplett weitergeleitet auf `web:8080`.
- `X-Forwarded-Proto` und `X-Forwarded-Host` setzen (Standard bei Traefik, Nginx Proxy Manager, Caddy).
- Request-Größe mindestens 2 MB (CSV-Import).
- Der Proxy muss aus einem privaten Netz kommen (Docker-Netz, LAN), sonst ignorieren Caddy und Tomcat die
  `X-Forwarded-*`-Header. Andernfalls `TRUSTED_PROXIES` setzen.

### Was der Web-Container regelt

- **PWA:** Deep Links (z. B. `/members/…`) liefern `index.html`; fehlende Dateien liefern 404.
- **Caching:** `index.html`, `ngsw.json`, Service Worker, Manifest und Icons mit `no-cache`, damit Updates
  ankommen; Dateien mit Hash im Namen ein Jahr `immutable`.
- **Sicherheits-Header:** Content-Security-Policy (nur eigene Quellen), `X-Frame-Options: DENY`,
  `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`.
- **Keycloak:** Admin-Konsole (`/auth/admin`) und Master-Realm (`/auth/realms/master`) sind gesperrt.

### Lokal bauen und prüfen

```bash
docker build -f backend/Dockerfile -t judo-portal-backend:local .
docker build -t judo-portal-web:local frontend

podman compose -f infra/compose.dev.yaml up -d         # Dev-Infrastruktur
infra/scripts/image-smoke-test.sh                      # startet beide Images und prüft sie
```

Die CI macht dasselbe im Job „Container-Images“ und pusht erst, wenn der Smoke-Test grün ist.
