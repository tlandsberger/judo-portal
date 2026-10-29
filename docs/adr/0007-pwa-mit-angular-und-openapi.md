# 0007 – PWA mit Angular, OpenAPI als API-Vertrag

- Status: angenommen (ersetzt [0001](0001-kotlin-multiplatform-clients.md), JSON-Teil von [0006](0006-api-vertrag-und-token-pruefung.md))
- Datum: 2026-10-29

## Kontext

Ursprünglich waren native Apps mit Kotlin Multiplatform / Compose geplant (ADR 0001). Das bringt
drei Build-Welten mit sich (Android-SDK, Xcode, Wasm), Store-Konten und eine noch junge
Web-Variante. Für ein Vereinsportal mit Formularen, Listen und Abrechnungen reicht eine Web-App,
die sich auf dem Handy wie eine App installieren lässt. Gleichzeitig soll der API-Vertrag
zwischen Backend und Client weiterhin abgesichert sein, wenn der Client nicht mehr in Kotlin geschrieben ist.

## Entscheidung

- **Client = Progressive Web App mit Angular** (TypeScript, Standalone-Komponenten, Angular Material,
  `@angular/pwa` für Service Worker und Manifest). Eine Codebasis für Browser, Android und iOS. Installiert
  wird über „Zum Startbildschirm hinzufügen“.
- **Login per Authorization Code + PKCE direkt im Browser** gegen Keycloak (Client
  `judo-portal-app`, Bibliothek `angular-auth-oidc-client`). Die Tokens liegen im `sessionStorage`
  (nur dieses Fenster, weg beim Schließen), nie im `localStorage`, dazu Refresh-Token-Rotation.
  Reiner Arbeitsspeicher geht nicht, weil der PKCE-Code-Verifier den Redirect zu Keycloak überstehen
  muss. Das Backend bleibt ein reiner Resource Server (ADR 0006).
- **Gleicher Origin:** Die PWA läuft unter `/`, die API unter `/api`. In Produktion stellt Caddy beides bereit,
  in der Entwicklung der Proxy des Angular-Dev-Servers (:4200 → :8080). Es gibt kein CORS im Backend.
- **API-Vertrag = OpenAPI.** springdoc erzeugt die Beschreibung aus dem Backend. Sie liegt als
  `api/openapi.json` im Repo, `OpenApiContractIT` hält Datei und Code synchron (CI rot bei Abweichung).
  Die PWA generiert ihre TypeScript-Typen aus dieser Datei.
  - Nicht-nullbare Kotlin-Felder sind im Schema `required`, nullbare sind `type: [..., "null"]`.
  - Swagger-UI unter `/swagger-ui.html` (ohne Login, enthält keine Daten).
- **JSON wieder über Jackson** (Spring-Standard), weil springdoc das Jackson-Modell beschreibt.
  Enum-Werte im JSON sind die Keycloak-Rollennamen (`@JsonValue`, z. B. `"trainer"`).
- Das KMP-Modul `shared-api` entfällt, die DTOs liegen im jeweiligen Backend-Modul.

## Konsequenzen

- ➕ Ein Frontend statt drei Build-Welten: kein Android-SDK, kein Xcode, keine Store-Konten, kein macOS-CI.
- ➕ Updates sind sofort bei allen Nutzern, ohne Store-Freigabe.
- ➕ Der Vertrag ist für jeden lesbar (Swagger-UI) und sprachunabhängig.
- ➖ Auf iOS gibt es kein automatisches Installations-Angebot (Mitglieder brauchen eine kurze Anleitung).
  Push-Benachrichtigungen dort nur bei installierter PWA (ab iOS 16.4).
- ➖ Keine Präsenz in App-Stores. Bei Bedarf lässt sich dieselbe PWA später mit Capacitor verpacken.
- ➖ Tokens im Browser-Speicher: Schutz vor XSS ist Pflicht (Angular-Sanitizing, strikte
  Content-Security-Policy in Caddy, Tokens nur im `sessionStorage`, nie im `localStorage`).

## Verworfene Alternativen

- **KMP / Compose Multiplatform (ADR 0001):** viel Build-Komplexität, die Web-Variante (Wasm) ist schwach bei
  Barrierefreiheit und Ladezeit.
- **React oder Vue:** gleichwertig möglich. Angular gibt mehr Struktur vor (Routing, Formulare, i18n,
  PWA eingebaut), das hilft wechselnden ehrenamtlichen Entwicklern.
- **Backend-for-Frontend (Login im Backend, Session-Cookie):** Kein Token im Browser, aber das Backend
  bräuchte Sessions und CSRF-Schutz. Für den Start zu aufwendig, bleibt eine Option für später.
- **Gemeinsame DTOs per Kotlin/JS-Export:** Das Frontend wäre an Kotlin-Tooling gekoppelt, OpenAPI ist der
  verbreitete Standard.
