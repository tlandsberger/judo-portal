# 0002 – Anmeldung in der App mit django-allauth

- Status: angenommen
- Datum: 2026-11-14

## Kontext

Mitglieder und Eltern sollen sich ohne Hürden anmelden, auch auf mehreren Geräten. Ein eigener Identity-Provider
(Keycloak) bedeutete zusätzliche Container, eine Realm-Konfiguration und eine zweite Admin-Oberfläche.

## Entscheidung

- **django-allauth** in der App: Passkeys (WebAuthn), Passwort (Argon2, mind. 10 Zeichen) und Anmeldecode per Mail.
- Alle Wege sind **gleichwertig und kombinierbar**: Ein Passkey ist ein eigener Anmeldeweg, kein erzwungener zweiter
  Faktor (`PortalAccountAdapter.get_login_stages`). Passkeys werden immer als anmeldefähig („passwordless“) angelegt.
- **Keine Selbstregistrierung:** Zugänge nur per Einladung (Link, 7 Tage gültig). Der Link wird erst per Klick
  angenommen, damit Link-Vorschauen in Mailprogrammen ihn nicht verbrauchen. Er zählt als frische Bestätigung, damit
  direkt danach ein Passkey angelegt werden kann.
- **Erster Administrator** über `PORTAL_INITIAL_ADMIN_EMAIL`, solange kein aktiver Administrator existiert.
- **Sitzungen** in der Datenbank, Cookie nur mit Sitzungs-ID (HttpOnly, Secure, SameSite=Lax), „Angemeldet bleiben“
  30 Tage gleitend. Übersicht und Abmelden anderer Geräte über `allauth.usersessions`.
- Rollen als feste Liste am Konto; die Administrator-Rolle schaltet die technische Verwaltung (Django-Admin) frei.

## Konsequenzen

- ➕ Kein separater Identity-Provider, alles in einer Datenbank und einem Container.
- ➕ Passkeys und Mail-Code machen Passwörter optional; „Passwort vergessen“ entfällt praktisch.
- ➖ Sicherheitsrelevante Updates von allauth müssen zeitnah eingespielt werden (Renovate, wöchentliches Release).
- ➖ Mailzustellung wird wichtig (Einladung, Codes) – produktiv über das IONOS-Postfach.

## Verworfene Alternativen

- **Keycloak:** mächtig, aber eigener Betrieb, Realm-Pflege, zweite Oberfläche.
- **Authentik der Homecloud:** würde Vereinskonten mit privaten Konten mischen.
- **Nur Passwort:** schlechtere Bedienung (vergessene Passwörter) und weniger sicher als Passkeys.
