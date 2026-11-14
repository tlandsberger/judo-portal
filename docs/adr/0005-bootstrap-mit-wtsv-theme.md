# 0005 – Bootstrap 5.3 mit WTSV-Theme

- Status: angenommen
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
