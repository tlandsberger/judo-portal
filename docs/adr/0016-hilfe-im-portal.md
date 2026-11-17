# 0016 – Hilfe im Portal

- Status: angenommen
- Datum: 2026-11-16

## Kontext

Mitglieder, Eltern, Übungsleiter und Abteilungsleitung brauchen eine Anleitung. Bisher gab es nur `docs/betrieb.md`
für den technischen Betrieb. Die Hilfe soll im Portal liegen, nur zeigen, was zum eigenen Zugang passt, und mit
Screenshots arbeiten, die nicht veralten.

## Entscheidung

- **App `portal.help`** mit Kapiteln in `chapters.py`. Wer ein Kapitel sieht, entscheiden die Rechte der Fach-Apps
  (`can_join_team`, `can_manage_events`, `can_manage_members`, `can_decide`, `can_manage_users`). Die Hilfe kennt
  diese Services, umgekehrt kennt niemand die Hilfe (nur Templates laden das Tag `help_link`).
- **Inhalte als Django-Templates** (`portal/help/templates/help/chapters/<slug>.html`) statt Markdown oder Wiki: keine
  neue Abhängigkeit, Links mit `{% url %}` brechen nicht unbemerkt, Gestaltung mit denselben Klassen wie das Portal.
- „Erste Schritte“ und „Fragen und Kontakt“ sind öffentlich (Link auf der Anmeldeseite). Fremde Kapitel ergeben 404.
- **Kontexthilfe:** `{% help_link "<slug>" %}` setzt ein „?“ neben die Überschrift wichtiger Seiten, nur wenn das
  Kapitel sichtbar ist.
- **Screenshots aus Playwright:** Das Projekt `hilfe` (`e2e/hilfe.spec.ts`) läuft nach allen anderen E2E-Tests, nutzt
  deren Daten und fotografiert die beschriebenen Seiten (Desktop und Handy, je hell und dunkel, JPEG). Die Hilfe zeigt
  per CSS das Bild zum gewählten Theme; ausgeblendete Bilder lädt der Browser dank `loading="lazy"` nicht. Mit `npm run help:screenshots`
  landen die Bilder in `portal/help/static/help/img` und werden committet. In der CI laufen die Abläufe mit, die Bilder
  werden aber nicht verglichen, weil Datumswerte täglich wechseln.
- Ein pytest-Test prüft, dass jedes in den Kapiteln verwendete Bild existiert – sonst scheitert in Produktion das
  Rendern (Manifest der statischen Dateien).

## Konsequenzen

- Bei sichtbaren Änderungen an beschriebenen Seiten gehören Hilfetext und Screenshots in denselben PR (CLAUDE.md).
- Die Bilder vergrößern das Repository um etwa 2 MB je vollständiger Neuerzeugung.

## Verworfene Alternativen

- **Markdown mit Renderer:** neue Abhängigkeit, Links nicht geprüft.
- **Externes Wiki oder PDF-Handbuch:** veraltet schnell, nicht an die Rechte gekoppelt.
- **Screenshots im CI vergleichen:** wegen wechselnder Daten dauerhaft instabil.
