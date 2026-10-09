# 0003 – Keycloak als Identity Provider, feste Rollen

- Status: angenommen
- Datum: 2026-10-09

## Kontext

Das Portal ist nur per Login erreichbar. Benötigt werden E-Mail/Passwort-Login,
Passwort-Reset, perspektivisch 2FA oder Passkeys, sowie ein sicherer Login-Flow für
native Apps und die Web-App. Funktionäre haben unterschiedliche Rechte.

## Entscheidung

- **Keycloak** (self-hosted) als OIDC-Identity-Provider mit eigenem Realm `judo`. Die
  Realm-Konfiguration wird als Export (`infra/keycloak/realm-judo.json`) versioniert.
- Alle Clients nutzen den **Authorization Code Flow mit PKCE** als *public clients*.
- Das Backend ist **OAuth2 Resource Server** und prüft JWTs über die JWKS von Keycloak.
- **Feste Realm-Rollen**, mehrere pro Person möglich:

  | Rolle | Zweck |
  |---|---|
  | `member` | Jedes Mitglied: eigene Daten, Events, An-/Abmeldungen |
  | `trainer` | Übungsleiter: eigene Gruppen, Anwesenheit, eigene Abrechnungen einreichen |
  | `board` | Vorstand: alle Mitgliedsdaten, vereinsweite Events, fachliche Freigabe von Abrechnungen |
  | `treasurer` | Kasse: Bankdaten, Auszahlung/Export freigegebener Abrechnungen |
  | `admin` | Technisch: Konten, Rollenvergabe, Systemeinstellungen, ohne fachliche Rechte |

- Keycloak **authentifiziert** und liefert die Rollen. Die **fachliche Autorisierung**
  (z. B. „Trainer sieht nur seine Gruppen“, „wer einreicht, darf nicht freigeben“) liegt im Backend.

## Konsequenzen

- ➕ Login-Seiten, Passwort-Reset, E-Mail-Verifikation, Brute-Force-Schutz, 2FA und Passkeys
  sind fertig vorhanden.
- ➕ Standard-OIDC, deshalb sind Clients und Backend nicht an Keycloak gebunden.
- ➖ Eine zusätzliche Komponente im Betrieb (Updates, Backup der Keycloak-DB).
- ➖ Feste Rollen sind weniger flexibel als feingranulare Berechtigungen. Für einen Verein dieser
  Größe reicht das. Ein späterer Wechsel auf Berechtigungen pro Funktion bleibt möglich, weil
  das Backend intern über Authorities prüft.
- Die Zuordnung Benutzerkonto ↔ Mitglied liegt im Backend (Modul `members`) über die
  Keycloak-User-ID (`sub`). Dass ein Konto mehrere Mitglieder vertritt (Eltern ↔ Kinder), wird bei
  der Mitgliederverwaltung entschieden.

## Verworfene Alternativen

- **Spring Authorization Server:** keine Zusatzkomponente, aber Login-UI, Reset- und
  Verifikations-Flows müssten selbst gebaut werden.
- **Managed IdP (Auth0, Zitadel Cloud …):** kein Betrieb, aber externe Abhängigkeit,
  mögliche Kosten und zusätzliche DSGVO-Prüfung.
- **Feingranulare Berechtigungen pro Funktion:** flexibler, aber für den Start unnötig komplex.
