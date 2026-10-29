# 0010 – Container-Images in der GitHub Container Registry

- Status: angenommen
- Datum: 2026-10-29

## Kontext

Das Portal soll per Docker (bzw. Podman) in der Homecloud laufen, die Images sollen öffentlich abrufbar sein.
In der Homecloud läuft bereits ein Reverse Proxy, der TLS und die Domains übernimmt. ADR 0005 hatte dafür noch
einen eigenen Caddy mit automatischem TLS auf Port 443 vorgesehen. Die Homecloud läuft auf amd64.

## Entscheidung

- **Zwei eigene Images**, Keycloak und PostgreSQL bleiben offizielle Images:
  - `ghcr.io/tlandsberger/judo-portal-backend`: Spring-Boot-Jar auf `eclipse-temurin:25-jre`, mehrstufig gebaut
    (`backend/Dockerfile`), Spring-Boot-Layer getrennt, läuft als Nicht-root-Nutzer auf Port 8080.
  - `ghcr.io/tlandsberger/judo-portal-web`: Caddy mit der gebauten PWA (`frontend/Dockerfile`, `frontend/Caddyfile`).
    Caddy liefert die PWA aus und leitet `/api` ans Backend und `/auth` an Keycloak weiter. So bleibt alles auf
    einer Adresse (keine CORS-Regeln, Token nur für die eigene API) und der vorgelagerte Proxy braucht nur eine
    Weiterleitung auf `web:8080`.
- **Kein TLS im Stack:** Caddy spricht nur HTTP auf Port 8080 (`auto_https off`). TLS macht der Reverse Proxy der
  Homecloud. `X-Forwarded-*` übernehmen Caddy und Tomcat nur von Absendern aus privaten Netzen.
- **Sicherheits- und Cache-Header** setzt Caddy: CSP ohne `unsafe-inline` für Skripte (dafür ist das Inlining von
  kritischem CSS in `angular.json` abgeschaltet), `no-cache` für `index.html`, `ngsw.json` und Service Worker,
  ein Jahr `immutable` für Dateien mit Hash im Namen.
- **Registry: GHCR, öffentlich.** Die CI pusht mit dem `GITHUB_TOKEN`, ohne weitere Secrets. Die Images enthalten
  keine Konfiguration oder Secrets, alles kommt per Umgebungsvariable.
- **Nur `linux/amd64`.**
- **Ablauf in der CI:** Der Job „Container-Images“ läuft erst nach Build, Frontend-Tests und E2E-Tests, baut beide
  Images, startet sie gegen die Dev-Infrastruktur (`infra/scripts/image-smoke-test.sh`) und pusht erst danach.
  Pull Requests bauen und prüfen nur.
- **Tags:** `sha-<commit>` bei jedem Push, der Branch-Name, `latest` auf dem Default-Branch, `1.2.3` und `1.2`
  bei Git-Tags `v1.2.3`. Produktiv wird ein fester Tag (`sha-…` oder Version) deployt, nicht `latest`.

## Konsequenzen

- ➕ Die Homecloud zieht fertige, getestete Images, dort wird nichts gebaut.
- ➕ Ein Umzug (anderer Host, anderer Proxy) braucht nur eine andere Compose-Datei.
- ➕ Ein Image für die PWA samt Routing: Die PWA bleibt unabhängig vom Backend aktualisierbar.
- ➖ Öffentliche Images: Jeder kann sie ziehen. Das ist unkritisch, weil der Quellcode keine Geheimnisse enthält,
  verlangt aber, dass das so bleibt.
- ➖ Neue GHCR-Pakete sind zunächst privat und müssen einmalig von Hand auf „public“ gestellt werden.
- Die Produktions-Compose (Keycloak-Konfiguration, Backup, Mailserver) folgt mit Schritt 9.

## Verworfene Alternativen

- **Docker Hub:** braucht ein zusätzliches Token als Secret, anonyme Pulls sind begrenzt.
- **Ein gemeinsames Image für PWA und Backend** (Spring liefert die statischen Dateien aus): koppelt die Releases
  und mischt Cache-/Header-Regeln der PWA in das Backend.
- **nginx statt Caddy:** gleichwertig, Caddy war in ADR 0005 schon gesetzt und hat die knappere Konfiguration.
- **Spring Boot Buildpacks (`bootBuildImage`):** weniger transparent als ein eigenes Dockerfile, schwerer an die
  eigenen Konventionen (Nicht-root-Nutzer, feste Basis-Images) anzupassen.
- **Multi-Arch (amd64 + arm64):** aktuell nicht nötig, lässt sich später über `platforms` ergänzen.
