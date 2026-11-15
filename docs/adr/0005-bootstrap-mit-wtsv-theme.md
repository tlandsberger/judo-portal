# 0005 – Bootstrap 5.3 mit WTSV-Theme

- Status: ersetzt durch [0008](0008-tailwind-und-daisyui.md) (App-Icon und Favicons gelten weiter)
- Datum: 2026-11-14

## Kontext

Das Erscheinungsbild folgt dem Design System „WTSV Judo“ (Farben, Schrift, Logos, Icons). Abstände, Radien und
Schatten sind frei. Hell und dunkel sind gefordert, Barrierefreiheit (WCAG AA) ebenso.

## Entscheidung

- **Bootstrap 5.3** (CSS-Variablen, Farbmodi hell/dunkel, barrierefreie Komponenten) mit eigenem Theme in
  `portal/static/css/theme.css`; keine Sass-Kompilierung.
- **Schrift Inter** (OFL, selbst gehostet) als freie Alternative zu Aptos, dessen Lizenz kein Einbetten erlaubt.
- **Icons:** Vereins-Piktogramme aus dem Design System (weiß im grünen Kreis) für Bereiche, Bootstrap Icons für
  Bedienelemente.
- Bibliotheken kommen aus npm (`package.json`) und werden von `scripts/vendor.mjs` nach `portal/static/vendor/`
  kopiert; so kann Renovate sie aktualisieren. Keine CDNs.

## Verworfene Alternativen

- **Eigene Baustein-Bibliothek:** dauerhafter Pflegeaufwand.
- **Tailwind + daisyUI:** modern, aber Build-Schritt und mehr Bewegung bei Versionen.
- **Web Awesome (ehem. Shoelace):** jünger, Teile kostenpflichtig.

## Nachtrag: App-Icon und Favicons

- **App-Icon** (Home-Bildschirm, Apple, Install-Hinweis): weißes Signet mit mattgrünen Akzenten auf Tiefgrün. Das
  Icon wird bei der Installation fest übernommen; das Web-App-Manifest kennt keine Variante für den dunklen Modus.
  Deshalb ein Design, das in beiden Modi trägt.
- **Favicon:** schwarzes bzw. weißes Signet ohne Hintergrund, per `media="(prefers-color-scheme: …)"`. Es folgt dem
  Modus des Browsers, nicht dem Portal-Schalter, weil die Tab-Leiste ebenfalls dem Browser folgt. `favicon.ico` im
  App-Icon-Design ist die Rückfallebene (z. B. Safari).
- Alle Dateien erzeugt `scripts/make_icons.py` aus den Masken in `assets/icons/`.
