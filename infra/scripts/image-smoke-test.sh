#!/usr/bin/env bash
# Smoke-Test der Container-Images (ADR 0010) gegen die laufende Dev-Infrastruktur (infra/compose.dev.yaml):
#  - startet das Backend-Image (Flyway gegen die Dev-Datenbank) und wartet auf /actuator/health = UP
#  - startet das Web-Image davor und prüft PWA, Deep Link, 404 für fehlende Dateien, Cache- und Security-Header
#    sowie die Weiterleitung von /api ans Backend und /auth an Keycloak
#
# Nutzung: BACKEND_IMAGE=… WEB_IMAGE=… infra/scripts/image-smoke-test.sh   (benötigt curl und podman oder docker)
set -euo pipefail

BACKEND_IMAGE="${BACKEND_IMAGE:-judo-portal-backend:local}"
WEB_IMAGE="${WEB_IMAGE:-judo-portal-web:local}"
NETWORK="${NETWORK:-judo-portal-dev_default}"
WEB_PORT="${WEB_PORT:-8090}"
BACKEND_PORT="${BACKEND_PORT:-8091}"
CONTAINER_TOOL="${CONTAINER_TOOL:-$(command -v podman >/dev/null && echo podman || echo docker)}"
WEB="http://localhost:${WEB_PORT}"

cleanup() {
    if [[ "${KEEP:-}" != "1" ]]; then
        "$CONTAINER_TOOL" rm -f smoke-backend smoke-web >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT
cleanup

"$CONTAINER_TOOL" run -d --name smoke-backend --network "$NETWORK" --network-alias backend -p "${BACKEND_PORT}:8080" \
    -e PORTAL_DB_URL=jdbc:postgresql://postgres:5432/portal \
    -e PORTAL_ISSUER_URI=http://keycloak:8081/realms/judo \
    -e PORTAL_KEYCLOAK_URL=http://keycloak:8081 \
    "$BACKEND_IMAGE" >/dev/null
"$CONTAINER_TOOL" run -d --name smoke-web --network "$NETWORK" -p "${WEB_PORT}:8080" \
    -e KEYCLOAK_URL=keycloak:8081 \
    "$WEB_IMAGE" >/dev/null

echo "Warte auf das Backend …"
for _ in $(seq 1 90); do
    if curl -fsS "http://localhost:${BACKEND_PORT}/actuator/health" 2>/dev/null | grep -q '"UP"'; then
        break
    fi
    sleep 2
done
if ! curl -fsS "http://localhost:${BACKEND_PORT}/actuator/health" | grep -q '"UP"'; then
    "$CONTAINER_TOOL" logs smoke-backend
    echo "FEHLER: Backend nicht gesund" >&2
    exit 1
fi
echo "OK  Backend: /actuator/health ist UP"

failed=0
# expect <Pfad> <Status> [<Header-Regex>]
expect() {
    local path="$1" status="$2" header="${3:-}" headers actual
    headers="$(curl -sS -o /dev/null -D - "${WEB}${path}")"
    actual="$(head -1 <<<"$headers" | awk '{print $2}')"
    if [[ "$actual" != "$status" ]]; then
        echo "FEHLER ${path}: Status ${actual}, erwartet ${status}" >&2
        failed=1
    elif [[ -n "$header" ]] && ! grep -qiE "$header" <<<"$headers"; then
        echo "FEHLER ${path}: Header /${header}/ fehlt" >&2
        failed=1
    else
        echo "OK  ${path} → ${status}${header:+ (${header})}"
    fi
}

expect / 200 '^content-security-policy: default-src .self.'
expect / 200 '^cache-control: no-cache'
expect /members 200 '^content-type: text/html'
expect /ngsw.json 200 '^cache-control: no-cache'
expect /gibt-es-nicht.js 404
main_js="$(curl -fsS "${WEB}/" | grep -oE 'main-[A-Za-z0-9_-]{8}\.js' | head -1)"
expect "/${main_js}" 200 '^cache-control: public, max-age=31536000, immutable'
expect /api/me 401
# Der Dev-Keycloak läuft ohne Pfad /auth: 404 kommt also von Keycloak, ein 502 hieße „nicht erreichbar“.
expect /auth/ 404

if [[ "$failed" != 0 ]]; then
    "$CONTAINER_TOOL" logs smoke-web
    exit 1
fi
echo "Alle Prüfungen bestanden."
