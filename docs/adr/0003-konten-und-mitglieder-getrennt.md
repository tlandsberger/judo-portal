# 0003 – Konten und Mitglieder getrennt, Verknüpfungen m:n

- Status: angenommen
- Datum: 2026-11-14

## Kontext

Eltern sollen ihre Kinder sehen, beide Elternteile jeweils, zusätzlich ihr eigenes Mitgliedsprofil – aber nicht das
des anderen Elternteils. Mitglieder bekommen ab 14 einen eigenen Zugang.

## Entscheidung

- **Benutzerkonto** (Anmeldung, Rollen) und **Mitglied** (Vereinsdaten) sind getrennte Modelle.
- Verbunden werden sie über **Verknüpfungen mit Art** (z. B. „eigenes Profil“, „Erziehungsberechtigt“), m:n:
  ein Konto ↔ mehrere Mitglieder, ein Mitglied ↔ mehrere Konten.
- Was ein Konto sieht, ergibt sich aus seinen Verknüpfungen und Rollen. Die Elternverknüpfung endet automatisch
  mit dem 18. Geburtstag des Kindes (wird bei jedem Zugriff geprüft).
- Umgesetzt mit dem Feature Mitgliederverwaltung (`portal.members`).

## Konsequenzen

- ➕ Familien, getrennt lebende Eltern und spätere Arten (z. B. Betreuer) ohne Umbau abbildbar.
- ➖ Sichtbarkeitsregeln brauchen sorgfältige Tests.
