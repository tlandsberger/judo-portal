# 0008 – Tailwind CSS und DaisyUI statt Bootstrap

- Status: angenommen
- Datum: 2026-11-15
- Ersetzt: [0005](0005-bootstrap-mit-wtsv-theme.md) (die Regeln zu App-Icon und Favicons gelten weiter)

## Kontext

Das Portal wirkte mit Bootstrap zu schlicht und zu sehr nach Standard. Gewünscht sind eine Seitennavigation statt
Kopf- und Fußleiste, kräftigere Farben und ein moderner Stack. Eigene Komponenten sollen nicht entstehen.

## Entscheidung

- **Tailwind CSS v4 mit DaisyUI 5.** DaisyUI liefert die Komponenten (`drawer`, `menu`, `navbar`, `card`, `btn`,
  `fieldset`/`input`, `alert`, `table`, `list`, `badge`, `modal`, `hero`). Sie werden so verwendet, wie DaisyUI sie
  dokumentiert: Formen, Rundungen und Größen bleiben auf dem Standard.
- **Angepasst sind nur die Farben**, als zwei DaisyUI-Themes in `portal/assets/app.css`:
  - Nur zwei Grüntöne (plus Abstufungen): Vereinsgrün (`primary`) und Dunkelgrün (`neutral`, ebenso `secondary`),
    dazu Gold (`accent`) und neutrale Flächen.
  - `wtsv-light`: helle, neutrale Flächen.
  - `wtsv-dark`: dunkle Flächen mit leichtem Grünstich, aufgehelltes Vereinsgrün, dasselbe Dunkelgrün. Das
    Vereinsgrün selbst hätte auf dunklem Grund als Text nur Kontrast 3,1–3,4 (AA verlangt 4,5).
  - Alle `*-content`-Farben erfüllen WCAG AA. Seitenleiste und Handy-Titelzeile stehen auf Dunkelgrün; dort gilt
    `neutral-content` als `base-content`, damit DaisyUIs Hover- und Fokusfarben passen.
- **Seitennavigation:** DaisyUI-`drawer`, am Desktop fest links (`lg:drawer-open`), am Handy über das Menü. Das
  funktioniert ohne JavaScript; `static/js/app.js` ergänzt nur Tastatur (Enter/Leertaste, Escape).
- **Schrift:** die Systemschrift (Tailwind `font-sans`), keine Schriftdateien mehr.
- **Formulare:** Djangos eigene Formular-Templates mit DaisyUI-Klassen (`portal/templates/django/forms/`,
  `FORM_RENDERER = TemplatesSetting`). Das geplante Paket `crispy-daisyui` (0.13) erzeugt noch Markup für DaisyUI 4
  (`form-control`, `label-text`) und passt deshalb nicht.
- **Build:** `npm run vendor` kopiert Icons und htmx und baut das CSS (`npm run css`, für die Entwicklung
  `npm run watch`) nach `portal/static/vendor/app.css`. Tailwind liest die Klassen aus `portal/templates` und
  `portal/static/js`. Der Docker-Build macht das in der Node-Stufe.
- **Icons** bleiben: Vereins-Piktogramme (`.pikto-*`, einziges eigenes CSS) und Bootstrap Icons als Icon-Schrift.

## Konsequenzen

- Klassen, die nur in Python-Code stehen, findet Tailwind nicht. Oberflächenklassen gehören in Templates oder
  `static/js`.
- Renovate hält Tailwind und DaisyUI als gemeinsame Gruppe aktuell. Neue DaisyUI-Versionen können das Aussehen
  ändern; die Screenshot-Tests fangen das ab.

## Verworfene Alternativen

- **Bei Bootstrap bleiben:** Seitennavigation wäre möglich, der Standard-Charakter bliebe.
- **Material Design 3:** Googles Web-Komponenten (`@material/web`) sind seit 2024 im Wartungsmodus; mit Tailwind
  hätten die Komponenten selbst gebaut werden müssen.
- **crispy-daisyui:** siehe oben.
