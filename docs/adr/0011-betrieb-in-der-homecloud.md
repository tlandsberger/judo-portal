# 0011 – Betrieb in der Homecloud (Portainer, Traefik, Cloudflare-Tunnel)

- Status: angenommen
- Datum: 2026-11-03

## Kontext

Die Homecloud (eigenes Repo `tlandsberger/homecloud`) betreibt alle Dienste als Docker-Stacks, die Portainer per
GitOps aus dem Repo deployt. Traefik terminiert TLS (Let's Encrypt per DNS-Challenge), von außen kommt der Verkehr
über einen Cloudflare-Tunnel, der alle Subdomains von `tlandsberger.de` zusätzlich per Cloudflare Access (E-Mail-OTP)
schützt. restic sichert täglich alle Docker-Volumes lokal und nach OneDrive, Renovate hält die Image-Tags aktuell.
ADR 0005 sah dagegen einen eigenen Caddy mit TLS, einen eigenen Backup-Container und eine Compose-Datei in diesem
Repo vor.

## Entscheidung

- **Stack im Homecloud-Repo:** `application/judo-portal/docker-compose.yml`, deployt von Portainer. Secrets nur als
  Portainer-Variablen. Dieses Repo liefert Images und Doku ([`deployment.md`](../deployment.md)).
- **Adressen:** `judo.tlandsberger.de` ist öffentlich (Cloudflare-Access-Bypass), den Login übernimmt Keycloak.
  Die Keycloak-Admin-Konsole läuft unter `judo-admin.tlandsberger.de` und bleibt hinter dem Cloudflare-OTP
  (`KC_HOSTNAME_ADMIN`, Frontend-URL des Master-Realms). Die Web-App sperrt `/auth/admin` und den Master-Realm.
- **Keycloak:** offizielles Image, Realm `judo` einmalig von Hand nach Checkliste. Kein Realm-Import in Produktion,
  damit keine Testkonfiguration und keine Secrets in Dateien landen.
- **Datenbanken:** je ein PostgreSQL-Container für Portal und Keycloak (Muster der übrigen Stacks).
- **Backup:** ein kleiner Dump-Container schreibt täglich konsistente `pg_dump`-Dateien in ein Volume, das restic
  ohnehin mitsichert. Kein eigener, verschlüsselter Backup-Container.
- **Releases:** Git-Tag `vX.Y.Z` → Images `X.Y.Z` → Renovate-PR im Homecloud-Repo. Patch und Minor werden
  automatisch gemergt und deployt, Major braucht eine Freigabe.
- **Mail:** SMTP eines IONOS-Postfachs, eingestellt im Realm. Kein eigener Mailserver: Mails von privaten
  Anschlüssen landen meist im Spam.

## Konsequenzen

- ➕ Das Portal fügt sich in Routing, TLS, Backup und Updates der Homecloud ein, ohne eigene Infrastruktur.
- ➕ Ein Release ist ein Git-Tag, der Rest läuft automatisch.
- ➖ Zwei Repos: Änderungen an Umgebungsvariablen müssen im Homecloud-Repo nachgezogen werden.
- ➖ Realm-Änderungen sind Handarbeit in der Admin-Konsole (Checkliste in `deployment.md` aktuell halten).
- ➖ Automatische Minor-Updates laufen ohne manuelle Abnahme live. Abgesichert durch die CI (Tests, E2E, Smoke-Test
  der Images) vor jedem Release.

## Verworfene Alternativen

- **Eigenes Keycloak-Image mit Prod-Realm:** reproduzierbarer, aber ein weiteres Image und Secrets-Platzhalter im
  Realm; der Realm wird selten geändert.
- **Authentik der Homecloud als IdP:** würde Vereinskonten mit privaten Konten mischen und die Einladungslogik
  (ADR 0009) neu erfordern.
- **Eigener SMTP-Server:** schlechte Zustellbarkeit von privaten IP-Adressen, kein Reverse-DNS.
