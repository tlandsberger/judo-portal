# Architektur – WTSV Judo

## Ziele

| Leitlinie | Umsetzung |
|---|---|
| **Erweiterbarkeit** | Eine Django-App pro Fachbereich, gemeinsame Rollen und Bausteine; neue Features docken an, ohne Bestehendes umzubauen |
| **Benutzerfreundlichkeit** | Handy zuerst, als App installierbar, hell/dunkel, barrierefrei (WCAG AA), Anmeldung ohne Passwortzwang (Passkey oder Code per Mail), Texte per Du |
| **Wartungsarm** | Wenige Abhängigkeiten, ein Container, SQLite statt Datenbankserver, Anmeldung eingebaut statt eigener Identity-Provider, automatische Updates, Tests und Releases |

## Überblick

```
Browser / installierte App (PWA)
        │ HTTPS
        ▼
Cloudflare-Tunnel ─▶ Traefik (TLS) ─▶ judo-portal (Docker)
                                      ├─ Gunicorn + Django (Seiten, Anmeldung, statische Dateien)
                                      ├─ Zeitplaner (Backup 02:00, Aufräumen)
                                      └─ /data: portal.sqlite3, backups/
                                      ──▶ IONOS-SMTP (Einladungen, Anmeldecodes)
```

- **Ein Container**, ein Volume. Keine weitere Infrastruktur (kein Datenbank-Container, kein Keycloak).
- **Seiten werden auf dem Server gerendert** (Django-Templates, Bootstrap). htmx ergänzt Teil-Aktualisierungen, wo
  es der Bedienung hilft.

## Module

| App | Inhalt |
|---|---|
| `portal.core` | App-Rahmen, Startseite, Bausteine, PWA (Manifest, Service Worker), Healthcheck, Backup, Zeitplaner |
| `portal.accounts` | Benutzerkonten, Rollen, Einladungen, Kontoverwaltung, Anpassungen an allauth |
| *(folgt)* `portal.members` | Mitglieder, CSV-Import, Verknüpfungen Konto ↔ Mitglied (m:n) |
| *(folgt)* `portal.events`, `portal.billing` | Termine, Übungsleiterabrechnung |

## Rollen und Rechte

| Rolle | Zweck |
|---|---|
| Mitglied (`member`) | Grundrolle für Vereinsmitglieder mit eigenem Zugang |
| Übungsleiter (`trainer`) | Trainer; Rechte kommen mit den Features Termine/Abrechnung |
| Abteilungsleiter (`department_head`) | Verwaltet Konten (einladen, Rollen außer Administrator), später Mitglieder |
| Administrator (`admin`) | Technische Rolle: alles, inkl. technischer Verwaltung (Django-Admin unter `/technik/`) |

Eltern sind keine Rolle: Ihr Konto wird mit den Kindern verknüpft. Was ein Konto sieht, ergibt sich aus Rollen und
Verknüpfungen; geprüft wird immer auf dem Server.

## Anmeldung

- Zugänge entstehen nur per **Einladung** (Mail mit Link, 7 Tage gültig). Den ersten Administrator lädt
  `PORTAL_INITIAL_ADMIN_EMAIL` beim Start ein.
- Anmeldewege, frei kombinierbar: **Passkey** (synchronisiert über iCloud/Google/Microsoft, an fremden Geräten per
  QR-Code), **Passwort** (Argon2, mind. 10 Zeichen), **Anmeldecode per E-Mail** (auch für „Passwort vergessen“).
- Sitzungen liegen in der Datenbank, der Browser hält nur die Sitzungs-ID (HttpOnly, Secure, SameSite). „Angemeldet
  bleiben“: 30 Tage ab letzter Nutzung. Schutz gegen Durchprobieren über allauth-Ratelimits.
- „Meine Anmeldung“ zeigt Passkeys, Passwort und angemeldete Geräte (andere Geräte abmelden).

## Erscheinungsbild

Design System „WTSV Judo“: Farben (`vereinsgruen` als Leitfarbe), Logos, Vereins-Piktogramme. Schrift: Inter als
freie Alternative zu Aptos (Aptos darf nicht eingebettet werden). Bootstrap 5.3 mit eigenem Theme
(`portal/static/css/theme.css`); hell als Standard, dunkel nach Geräteeinstellung oder Umschalter.

## Sicherheit und Datenschutz

- Content Security Policy ohne Inline-Skripte, keine externen Quellen (keine CDNs, keine fremden Schriften).
- HSTS, `X-Frame-Options: DENY`, sichere Cookies, CSRF-Schutz.
- Datensparsamkeit: keine Bankdaten, keine Graduierungen (Doku-Me), keine Kontaktdaten der Eltern am Kind.
- Später: Änderungsprotokoll, Export der eigenen Daten, Löschung nach Austritt.

## Qualität und Wartung

- **CI** bei jedem Push: Conventional Commits, ruff, mypy, Migrationen, pytest, Image-Bau, Smoke-Test,
  E2E (Playwright) mit axe-Barrierefreiheitsprüfung und Screenshot-Vergleich (hell/dunkel, Desktop/Handy).
- **Renovate** aktualisiert Python-, npm-, Docker- und Action-Versionen; Patch/Minor werden automatisch gemergt,
  wenn alle Tests grün sind.
- **Release** jeden Sonntag 23 Uhr, wenn es neue Commits gibt: Version aus den Commits, Tag, GitHub-Release mit
  Changelog, Image `ghcr.io/tlandsberger/judo-portal`. Renovate in der Homecloud zieht die neue Version nach, Portainer
  deployt.
- **Live-Check** täglich gegen die Produktivseite.

## Roadmap

| # | Schritt | Status |
|---|---|---|
| 1 | Fundament: Anmeldung, Rollen, Einladungen, Design, CI/CD, Betrieb | ✅ |
| 2 | Mitgliederverwaltung inkl. CSV-Import und Zugängen für Mitglieder/Eltern | geplant |
| 3 | Termine (Trainings, Veranstaltungen) | offen |
| 4 | Übungsleiterabrechnung | offen |
| 5 | Datenschutz-Funktionen (Änderungsprotokoll, Export, Löschung) | offen |
