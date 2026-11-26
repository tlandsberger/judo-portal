# 0027 – DaisyUI statt eigener Lösungen: Theme Controller, Footer

- Status: angenommen
- Datum: 2026-11-26
- Ergänzt: [0008](0008-tailwind-und-daisyui.md), [0017](0017-einheitliche-bedienung.md)

## Kontext

An zwei Stellen hatten wir eigene Bausteine, für die DaisyUI 5 eine Komponente mitbringt:

- Den Wechsel zwischen hellem und dunklem Design erledigte ein Button, dessen Symbol und Beschriftung `app.js` umschrieb.
- Die Fußzeile war ein eigenes Flex-Layout.

## Entscheidung

- **Theme Controller:** Der Umschalter ist ein Kontrollkästchen `theme-controller` mit dem Wert `wtsv-dark` in einem
  `swap`. Symbol und Text zeigen, wohin der Klick wechselt: im hellen Design der Mond und „Dunkles Design“, im dunklen
  die Sonne und „Helles Design“ – in der Seitenleiste mit Text, auf den Eingangsseiten als runder Button. Das Design
  wechselt DaisyUI per CSS (`:root:has(input.theme-controller[value=wtsv-dark]:checked)`).
  JavaScript braucht es nur noch für zweierlei: `theme-init.js` setzt vor dem ersten Zeichnen `data-theme` aus der
  gespeicherten Wahl oder der Geräteeinstellung, `app.js` speichert die Wahl in `localStorage` und hält alle Umschalter
  einer Seite gleich – sofort beim Laden, damit der Swap nicht sichtbar überblendet. Das Backend kennt das Design nicht.
- **Footer:** `footer sm:footer-horizontal`, am Handy untereinander.

## Konsequenzen

- Für Screenreader heißt das Kontrollkästchen immer „Dunkles Design“ und ist im dunklen Design angehakt; der sichtbare
  Text ist ausgeblendet, damit nicht beide Beschriftungen vorgelesen werden.

## Verworfene Alternativen

- **OTP für Codes:** Der Anmeldecode von allauth hat acht Zeichen aus Buchstaben mit Bindestrich, der Code von der
  Ausschreibung ist kein Einmalcode. Ein Umstellen der allauth-Codes auf Ziffern nur für die Komponente lohnt nicht.
- **Avatar-Platzhalter mit Initialen** in Seitenleiste und Personenlisten: wirkte neben den kleinen Symbolen der
  Seitenleiste unruhig; vorerst zurückgestellt.
- Theme Controller als `toggle`: Sonne und Mond sind auf allen Seiten gleich und ohne Beschriftung verständlich.
