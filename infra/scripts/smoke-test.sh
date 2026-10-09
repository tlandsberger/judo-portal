#!/usr/bin/env bash
# Smoke-Test der lokalen Dev-Umgebung (infra/compose.dev.yaml):
#  - wartet, bis Keycloak den Realm "judo" ausliefert
#  - holt für jeden Testnutzer ein Token und prüft dessen Portal-Rollen
#  - prüft, dass die Backend-Datenbank "portal" erreichbar ist
#
# Nutzung: infra/scripts/smoke-test.sh   (benötigt curl, jq und podman oder docker)
set -euo pipefail

KEYCLOAK_URL="${KEYCLOAK_URL:-http://localhost:8081}"
REALM="judo"
CLIENT_ID="judo-dev-tools"
PASSWORD="test"
COMPOSE_FILE="$(cd "$(dirname "$0")/.." && pwd)/compose.dev.yaml"
CONTAINER_TOOL="${CONTAINER_TOOL:-$(command -v podman >/dev/null && echo podman || echo docker)}"

# Erwartete Portal-Rollen je Testnutzer (sortiert, kommagetrennt).
declare -A EXPECTED=(
    [mitglied]="member"
    [trainer]="member,trainer"
    [vorstand]="board,member"
    [kasse]="member,treasurer"
    [admin]="admin"
)
PORTAL_ROLES='["member","trainer","board","treasurer","admin"]'

echo "Warte auf Keycloak (${KEYCLOAK_URL}/realms/${REALM}) …"
for _ in $(seq 1 90); do
    if curl -fsS "${KEYCLOAK_URL}/realms/${REALM}/.well-known/openid-configuration" >/dev/null 2>&1; then
        break
    fi
    sleep 2
done
curl -fsS "${KEYCLOAK_URL}/realms/${REALM}/.well-known/openid-configuration" >/dev/null

failed=0
for user in "${!EXPECTED[@]}"; do
    token=$(curl -fsS "${KEYCLOAK_URL}/realms/${REALM}/protocol/openid-connect/token" \
        -d grant_type=password -d client_id="${CLIENT_ID}" \
        -d username="${user}@test.local" -d password="${PASSWORD}" | jq -r .access_token)

    # JWT-Payload (Base64URL) dekodieren und nur die Portal-Rollen betrachten.
    payload=$(cut -d. -f2 <<<"${token}" | tr '_-' '/+')
    while (( ${#payload} % 4 )); do payload+="="; done
    actual=$(base64 -d <<<"${payload}" |
        jq -r --argjson portal "${PORTAL_ROLES}" \
            '[.realm_access.roles[] | select(. as $r | $portal | index($r))] | sort | join(",")')

    if [[ "${actual}" == "${EXPECTED[$user]}" ]]; then
        echo "  OK    ${user}@test.local → ${actual}"
    else
        echo "  FEHLER ${user}@test.local → '${actual}', erwartet '${EXPECTED[$user]}'"
        failed=1
    fi
done

echo "Prüfe Datenbank 'portal' …"
if "${CONTAINER_TOOL}" compose -f "${COMPOSE_FILE}" exec -T postgres \
    psql -U portal -d portal -tAc "select current_user" | grep -qx portal; then
    echo "  OK    Datenbank portal erreichbar"
else
    echo "  FEHLER Datenbank portal nicht erreichbar"
    failed=1
fi

if (( failed )); then
    echo "Smoke-Test FEHLGESCHLAGEN"
    exit 1
fi
echo "Smoke-Test erfolgreich"
