# 0007 – Betrieb als ein Container in der Homecloud

- Status: angenommen
- Datum: 2026-11-14

## Entscheidung

- Stack `application/judo-portal/docker-compose.yml` im Repo `tlandsberger/homecloud`, deployt von Portainer (GitOps).
- **Ein Container** `judo_portal` mit Volume `/data`; Traefik-Labels für `judo.tlandsberger.de` (öffentlich über den
  Cloudflare-Tunnel mit Access-Bypass). Die technische Verwaltung (`/technik/`) ist nur für Administratoren.
- Konfiguration über Portainer-Variablen (`PORTAL_*`), siehe `docs/betrieb.md`.
- Updates: neues Image-Release → Renovate-PR in der Homecloud → automatischer Merge (Patch/Minor) → Portainer deployt.
