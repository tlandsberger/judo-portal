# 0001 – Kotlin Multiplatform + Compose Multiplatform für alle Clients

- Status: angenommen
- Datum: 2026-10-09

## Kontext

Das Portal soll als Web-App sowie als native Android- und iOS-App verfügbar sein. Der
Verein hat begrenzte Entwicklungskapazität, deshalb soll möglichst wenig Code mehrfach
geschrieben werden. Das Backend wird in Kotlin entwickelt ([0002](0002-spring-boot-kotlin-backend.md)).

## Entscheidung

Alle drei Clients werden mit **Kotlin Multiplatform (KMP)** und **Compose Multiplatform**
gebaut, mit den Targets Android, iOS und Web (Kotlin/Wasm, `wasmJs`).

- Eine gemeinsame UI-Codebasis (`client/composeApp`) und eine gemeinsame Logikschicht
  (`client/shared`: API-Client, Repositories, ViewModels).
- Plattformspezifischer Code nur über `expect`/`actual` für Login-Flow, sichere Token-Ablage
  und später Push.
- Das KMP-Modul `shared-api` enthält die API-DTOs und wird auch vom Backend genutzt.

## Konsequenzen

- ➕ Eine Sprache von der Datenbank bis zur UI, DTOs ohne Code-Generierung geteilt.
- ➕ Ein UI-Code für drei Plattformen, die Apps sind echte native Store-Apps.
- ➖ Die Web-App ist beim ersten Laden größer als eine klassische JS-App und braucht einen
  aktuellen Browser (WasmGC). Barrierefreiheit und Textauswahl im Web sind schwächer als bei
  HTML-basierten Frameworks. Hinter einem Login und bei bekannter Zielgruppe ist das akzeptabel.
- ➖ Für iOS-Builds wird macOS benötigt (lokal oder als CI-Runner), für die Veröffentlichung ein
  Apple-Developer-Konto.
- Falls das Web-Erlebnis später nicht reicht, kann eine separate Web-UI auf derselben API
  und demselben `shared-api` aufsetzen. Die Architektur lässt das zu.

## Verworfene Alternativen

- **Expo/React Native + Web (TypeScript):** sehr reif und starkes Web, aber zweite Sprache
  neben dem Kotlin-Backend und kein geteilter Vertrag ohne Code-Generierung.
- **Flutter:** eine Codebasis für alle drei Plattformen, aber Dart als zusätzliche Sprache und
  kein Code-Sharing mit dem Backend.
- **KMP-Logik + separate Web-UI (z. B. Angular/React):** bestes Web-Erlebnis, aber zwei
  UI-Codebasen. Bleibt als Option für später.
- **PWA + Capacitor:** am günstigsten, aber weniger natives Verhalten.
