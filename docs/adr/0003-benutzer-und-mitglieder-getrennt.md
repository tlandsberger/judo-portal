# 0003 – Benutzer und Mitglieder getrennt, Verknüpfungen m:n

- Status: angenommen
- Datum: 2026-11-14

## Kontext

Eltern sollen ihre Kinder sehen, beide Elternteile jeweils, zusätzlich ihr eigenes Mitgliedsprofil – aber nicht das
des anderen Elternteils. Mitglieder bekommen ab 14 einen eigenen Zugang.

## Entscheidung

- **Benutzer** (Anmeldung, Rollen) und **Mitglied** (Vereinsdaten) sind getrennte Modelle.
- Verbunden werden sie über **Verknüpfungen mit Art** (z. B. „eigenes Profil“, „Erziehungsberechtigt“), m:n:
  ein Benutzer ↔ mehrere Mitglieder, ein Mitglied ↔ mehrere Benutzer.
- Was ein Benutzer sieht, ergibt sich aus seinen Verknüpfungen und Rollen. Die Elternverknüpfung endet automatisch
  mit dem 18. Geburtstag des Kindes (wird bei jedem Zugriff geprüft).
- Umgesetzt mit dem Feature Mitgliederverwaltung (`portal.members`, Details in ADR 0009).

## Konsequenzen

- ➕ Familien, getrennt lebende Eltern und spätere Arten (z. B. Betreuer) ohne Umbau abbildbar.
- ➖ Sichtbarkeitsregeln brauchen sorgfältige Tests.
