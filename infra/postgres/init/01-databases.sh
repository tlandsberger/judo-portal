#!/usr/bin/env bash
# Legt beim ersten Start je eine Datenbank mit eigenem Nutzer für Backend und Keycloak an.
# Läuft nur, solange das Daten-Volume leer ist (Neuanlage: compose down -v).
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
    -v portal_pw="$PORTAL_DB_PASSWORD" \
    -v keycloak_pw="$KEYCLOAK_DB_PASSWORD" <<-'EOSQL'
	CREATE ROLE portal LOGIN PASSWORD :'portal_pw';
	CREATE DATABASE portal OWNER portal;

	CREATE ROLE keycloak LOGIN PASSWORD :'keycloak_pw';
	CREATE DATABASE keycloak OWNER keycloak;
EOSQL
