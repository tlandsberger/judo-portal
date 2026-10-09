# 0005 – Betrieb per Docker Compose in der Homecloud

- Status: angenommen
- Datum: 2026-10-09

## Kontext

Das Portal soll zunächst in einer vorhandenen, container-basierten Homecloud laufen.
Ein späterer Umzug (z. B. auf einen EU-VPS) soll ohne Architekturänderung möglich sein.
Die mobilen Apps müssen das Backend aus dem Internet erreichen.

## Entscheidung

- Alle Komponenten werden als **OCI-Container** ausgeliefert und mit **Docker Compose**
  betrieben: `caddy` (Reverse Proxy, TLS, Web-Bundle), `backend`, `keycloak`, `postgres`,
  `backup`.
- Die Images werden in GitHub Actions gebaut und in der **GitHub Container Registry (GHCR)**
  abgelegt.
- Nach außen wird nur Port 443 über Caddy exponiert. Routing: `/` → Web-App,
  `/api` → Backend, `/auth` → Keycloak.
- Konfiguration und Secrets kommen über Umgebungsvariablen bzw. Docker-Secrets, nie aus dem Repo.
- Ein regelmäßiges, verschlüsseltes `pg_dump`-Backup beider Datenbanken läuft mit Rotation.

## Konsequenzen

- ➕ Kaum laufende Kosten, volle Datenhoheit.
- ➕ Portabel: Dieselben Images laufen auf jedem Container-Host, ein Umzug braucht nur andere
  Compose-Files bzw. Manifeste.
- ➖ Verfügbarkeit hängt am Heimanschluss und an der Hardware. Für ein Vereinsportal
  ist das vertretbar, sollte aber transparent kommuniziert werden.
- ➖ Erreichbarkeit von außen nötig: DynDNS + Portfreigabe oder ein Tunnel (z. B. Cloudflare
  Tunnel). Die Entscheidung fällt beim Produktiv-Deployment.
- Die genaue Laufzeitumgebung der Homecloud (Docker Compose, Portainer, k3s,
  Unraid/Synology …) ist noch zu klären. Docker Compose ist die gemeinsame Basis.

## Verworfene Alternativen

- **EU-VPS (z. B. Hetzner) sofort:** kleine monatliche Kosten, bleibt Option für später.
- **Managed PaaS:** weniger Administration, aber höhere Kosten und Anbieterbindung.
