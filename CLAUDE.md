# CLAUDE.md – judo-portal

Vereinsportal „Wedeler TSV Judo“ (Django, eine App pro Fachbereich). Architektur: `docs/ARCHITECTURE.md`,
Entscheidungen: `docs/adr/`, Betrieb: `docs/betrieb.md`.

## Arbeitsweise

- Pro Feature werden die fachlichen Anforderungen geplant und freigegeben; danach freie Hand bei der Umsetzung.
  Vorher melden nur bei offenen fachlichen Fragen, Auswirkungen auf den Betrieb (Homecloud, Datenbank, Mail) oder
  nicht umkehrbaren Schritten (Release, Merge, Löschen).
- Technische Entscheidungen trifft Claude selbst und hält sie als ADR fest.
- Ist eine Änderung fertig und lokal geprüft (ruff, mypy, pytest, E2E bei Änderungen an der Oberfläche), erstellt
  Claude den PR selbst, ohne nachzufragen. Merge und Release entscheidet weiterhin der Maintainer.
- Doku, Kommentare und Oberflächentexte auf Deutsch (Du-Form), Code-Bezeichner englisch.

## Befehle

```bash
uv sync && npm ci && npm run vendor          # vendor baut auch das CSS; beim Arbeiten an Templates: npm run watch
PORTAL_DEBUG=true uv run python manage.py runserver
uv run ruff format . && uv run ruff check --fix . && uv run mypy portal && uv run pytest
uv run python manage.py makemigrations          # nach Modelländerungen, Migration mit committen
```

E2E (Docker nötig): siehe `e2e/README.md`. Nach gewollten Design-Änderungen die Screenshots mit
`--update-snapshots` im Playwright-Container neu erzeugen und committen.

## Begriffe

- In Oberfläche und E-Mails heißt das Portal immer **„Wedeler TSV Judo“**; die Abkürzung „WTSV“ nur im Code.
- **„Benutzer“** (Code: `user`) für alle, die sich anmelden können – nicht „Konto“. Wo es um den eigenen Zugang
  geht, passt auch „Zugang“. Mitglieder (Vereinsdaten) sind etwas anderes.
- **„Push-Benachrichtigung“** – nie „Push“ allein oder „Push-Nachricht“; im Code `push_notification` /
  `PushNotification…` (Namen von Bibliotheken und Browser-APIs bleiben).
- Passkeys heißen „Passkey“, nicht „Sicherheitsschlüssel“. Texte von allauth und anderen Paketen passen wir über
  `portal/locale/de/LC_MESSAGES/django.po` an (Du-Form, Begriffe wie oben); danach
  `uv run pybabel compile -d portal/locale -D django` und die `.mo` mit committen.

## Regeln

- **Commits:** Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `ci:`, `chore:` …). `feat` = Minor,
  `fix` = Patch, `!`/`BREAKING CHANGE` = Major. Die CI prüft das, das Release entsteht daraus automatisch.
- **Module:** neue Fachbereiche als eigene App unter `portal/<bereich>/` (Modelle, Services, Views, Templates, Tests).
  Fachlogik in `services.py`, Views schlank. Querverweise zwischen Apps nur über deren Services/Modelle, nicht über Views.
- **Rechte:** fest definierte Rollen in `portal/accounts/models.py` (`Role`). Prüfen auf dem Server mit
  `role_required` bzw. `user.has_role(...)` (`portal/accounts/permissions.py`). Anzeige in Templates spiegelt das.
- **Benutzer und Mitglieder sind getrennt;** Verknüpfungen (eigenes Profil, Erziehungsberechtigt …) sind m:n.
  Sichtbarkeit von Mitgliedern nur über `portal/members/services.py` (`visible_members`, `can_self_edit` …).
  `portal.accounts` kennt die anderen Apps nicht; sie docken über Signale an (`portal/accounts/signals.py`).
- **Veranstaltungen:** Zielgruppen-Matching, Teilnahme mit Rollen und Rechte (`can_take_role`, `can_lead`,
  `can_see_participants`) nur über `portal/events/services.py`. Eine Teilnahme je Mitglied und Termin; Rollen und
  Arten sind Daten, keine Konstanten (ADR 0012). Das Team sieht Mitgliederdaten nur in der Teilnehmerliste eigener
  Termine. Begriffe: „Co-Trainer“, „Stunden bestätigen“.
- **Abrechnung:** Sätze, Monate, Einreichen und Freigabe nur über `portal/billing/services.py` (ADR 0014). Zeilen
  sind Schnappschüsse; Termine eingereichter Monate sperrt `billing` über `events.services.register_lock`.
- **Datenschutz:** Wer personenbezogene Daten ändert, protokolliert das mit `portal.core.audit.log` (bei Feldern mit
  `snapshot`/`diff`; ADR 0015). Auskunft und Löschen nur über `portal/privacy/services.py`; neue Daten zu Mitgliedern
  oder Benutzern dort in `export_*` aufnehmen und beim Löschen mitnehmen.
- **Benachrichtigungen:** Tägliches nur über `portal.notifications.services.notify` (Push-Benachrichtigung, sonst Mail; Schlüssel je
  Anlass, damit nichts doppelt rausgeht). Einladung, Anmeldecode, Sicherheit des Zugangs und neue Verknüpfungen
  immer direkt per Mail (ADR 0011). Gäste haben keinen Benutzer: alles an sie per Mail über
  `portal/events/guests.py` (ADR 0013). Wiederkehrende Jobs über `portal.core.scheduler.register_periodic`.
- **Anmeldung:** django-allauth; Passkey, Passwort und Mail-Code sind gleichwertig (kein erzwungener zweiter Faktor,
  siehe `PortalAccountAdapter`). Keine Selbstregistrierung, Zugänge nur per Einladung.
- **Oberfläche:** Tailwind CSS mit DaisyUI (ADR 0008). DaisyUI-Komponenten so verwenden, wie sie dokumentiert sind,
  nichts umbiegen; Tailwind-Klassen für Layout. Farben nur über die DaisyUI-Farbrollen (`primary`, `neutral`,
  `base-*` …) der Themes `wtsv-light`/`wtsv-dark` in `portal/assets/app.css`, beide prüfen. Nach neuen Klassen
  `npm run css` (oder `npm run watch`). Vereins-Piktogramme als `.pikto .pikto-<name>`,
  Bedien-Icons aus Bootstrap Icons. App-Icon und Favicons nur über `scripts/make_icons.py` erzeugen
  (`uv run --with pillow python scripts/make_icons.py`). Keine Inline-Skripte oder -Styles (CSP); JavaScript als Datei unter `static/js/`.
  Keine externen CDNs oder Schriften.
- **Hilfe:** Ändert sich eine in der Hilfe beschriebene Seite oder ein Ablauf sichtbar, im selben PR das Kapitel in
  `portal/help/templates/help/chapters/` anpassen und die Screenshots mit `npm run help:screenshots` (im
  Playwright-Container, siehe `e2e/README.md`) neu erzeugen. Neue Bereiche bekommen ein Kapitel (ADR 0016).
- **Barrierefreiheit:** WCAG AA; neue Seiten in `e2e/pages.spec.ts` mit axe prüfen.
- **Tests:** pytest für Fachlogik und Rechte (`portal/<app>/tests/`), E2E für wichtige Abläufe.
- **Datenbank:** SQLite; Änderungen nur über Django-Migrationen. Lange Schreibtransaktionen vermeiden.
- **Konfiguration** nur über `PORTAL_*`-Umgebungsvariablen (`portal/settings.py`, `docs/betrieb.md`).
- **Abhängigkeiten:** Python in `pyproject.toml`/`uv.lock`, Frontend-Bibliotheken in `package.json`
  (kopiert bzw. gebaut von `npm run vendor`). Renovate hält alles aktuell.
- **Produktion:** Stack im Repo `tlandsberger/homecloud` (`application/judo-portal/`). Neue Umgebungsvariablen dort
  nachziehen.
