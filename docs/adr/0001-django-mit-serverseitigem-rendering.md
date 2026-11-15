# 0001 – Django mit serverseitigem Rendering und htmx

- Status: angenommen
- Datum: 2026-11-14

## Kontext

Das Portal wird neu aufgebaut. Leitlinien: Erweiterbarkeit, Benutzerfreundlichkeit, möglichst wenig Wartung bei
hoher Automatisierung. Nutzer sind vor allem Mitglieder und Eltern (überwiegend lesend, am Handy) und wenige
Funktionäre (pflegend). Die Vorgängerversion (Spring Boot + Angular + Keycloak) brauchte zwei Ökosysteme, einen
API-Vertrag und mehrere Container.

## Entscheidung

- **Django** (aktuelle Version, Renovate führt Minor-Updates automatisch nach) mit Python (aktuelle Version, Image und `requires-python` gemeinsam).
- **Seiten vom Server** (Django-Templates), **htmx** für Teil-Aktualisierungen, kein eigener Frontend-Build.
- **Eine App pro Fachbereich** (`portal/<bereich>/`), Fachlogik in Services, Rechte zentral.
- **PWA:** Manifest und schlanker Service Worker (installierbar, Offline-Hinweis). Offline-Arbeit nur, wenn ein
  Feature sie braucht – dann als gezielte Insel auf einer Seite.
- Typprüfung mit mypy/django-stubs, Format/Lint mit ruff.

## Konsequenzen

- ➕ Eine Sprache, ein Container, wenige Abhängigkeiten, ausgereifte Bausteine (Admin, Formulare, Migrationen).
- ➕ Weniger Code pro Feature: kein API-Vertrag, keine doppelte Validierung.
- ➖ Weniger „App-artig“ als eine SPA (z. B. kein sofortiges Umschalten ohne Server-Antwort, offline nur eingeschränkt).
- ➖ Python ist dynamisch typisiert – ausgeglichen durch mypy und Tests.

## Verworfene Alternativen

- **Spring Boot + Angular:** sehr robust, aber zwei Ökosysteme, API-Vertrag, höchste Code- und Update-Last.
- **SvelteKit (TypeScript):** schlank und app-artig, aber mehr Bewegung im npm-Ökosystem, jüngere Login-Bibliotheken.
- **ASP.NET Core + Blazor:** gute Alternative mit strengen Typen; mehr Code als Django, weniger fertige Bausteine.
