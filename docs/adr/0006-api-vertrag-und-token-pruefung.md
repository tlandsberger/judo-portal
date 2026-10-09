# 0006 – API-Vertrag & Token-Prüfung

- Status: angenommen
- Datum: 2026-10-09

## Kontext

Das Backend stellt eine REST-API für drei Clients bereit (Android, iOS, Web). Die Clients sind in
Kotlin geschrieben und nutzen die DTOs aus `shared-api` mit kotlinx.serialization. Keycloak stellt
Tokens für mehrere Clients aus ([0003](0003-keycloak-identity.md)). Das Backend soll nur Tokens
akzeptieren, die für die Portal-API gedacht sind.

## Entscheidung

- **JSON-Format = kotlinx.serialization.** Das Backend serialisiert die `@Serializable`-DTOs aus
  `shared-api` mit kotlinx.serialization, über den Spring-Boot-Starter
  `spring-boot-starter-kotlinx-serialization-json`. Für diese Typen greift er vor Jackson. Damit gelten
  auf beiden Seiten dieselben Regeln, z. B. Rollen als `"trainer"` (`@SerialName`). Jackson bleibt
  nur für Spring-interne Antworten (Actuator, Fehler).
  - Felder mit Default-Wert lässt kotlinx weg (`email = null`, `roles = []`). Clients mit
    `shared-api` setzen die Defaults beim Lesen wieder ein. Fremde Clients müssen fehlende
    Felder als Default behandeln.
- **Audience-Prüfung:** Ein Audience-Mapper in Keycloak schreibt `judo-portal-api` in die
  Access-Tokens der Portal-Clients. Das Backend akzeptiert nur Tokens mit dieser Audience
  (`spring.security.oauth2.resourceserver.jwt.audiences`). Zusätzlich prüft es Signatur (JWKS),
  Issuer und Ablauf.
- **Rollen** kommen aus `realm_access.roles`. Übernommen werden nur die fünf festen Portal-Rollen
  (als `ROLE_MEMBER` …), alle anderen Keycloak-Rollen werden ignoriert. Ein Token ohne `sub` wird
  abgelehnt.
- **Fachcode sieht keine Tokens:** Controller erhalten `CurrentUser` (Modul `shared`) als Parameter.
- **Fehler** werden als RFC-9457-ProblemDetail ausgeliefert. 401 kommt mit `WWW-Authenticate`.
  Pfade außerhalb von `/api/**` und `/actuator/health` sind gesperrt.

## Konsequenzen

- ➕ Kein Format-Drift zwischen Backend und Apps, ein Test (`MeControllerTest`) sichert das ab.
- ➕ Ein gestohlenes Token eines anderen Clients im selben Realm funktioniert an der API nicht.
- ➖ Jeder neue Client, der die API aufrufen soll, braucht den Audience-Mapper.
- ➖ Fremde API-Nutzer müssen das Weglassen von Default-Feldern kennen. Das steht in der
  OpenAPI-Doku, sobald sie eingerichtet ist.

## Verworfene Alternativen

- **Jackson für alles:** Jackson kennt `@SerialName` nicht, die Rollen kämen als `"TRAINER"`.
  Man müsste die Regeln doppelt pflegen.
- **Keine Audience-Prüfung:** Dann würde jedes gültige Token des Realms akzeptiert, auch das eines
  späteren Fremd-Clients.
