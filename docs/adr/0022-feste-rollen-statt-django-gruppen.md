# 0022 – Feste Rollen statt Django-Gruppen und -Berechtigungen

- Status: angenommen
- Datum: 2026-11-19
- Ergänzt: [0002](0002-anmeldung-in-der-app.md) („Rollen als feste Liste am Benutzer“)

## Kontext

Django bringt für die Autorisierung Gruppen und Berechtigungen mit (`Group`, `Permission`, `PermissionsMixin`). Sie
erscheinen auch in der technischen Verwaltung (`/technik/`). Das Portal nutzt sie nicht; die Begründung stand bisher nur
in einem Satz in ADR 0002.

Die Rechte im Portal sind von zwei Arten:

- **Grob, nach Vereinsfunktion:** Wer Mitglieder, Benutzer und Veranstaltungen verwaltet (Abteilungsleitung), wer
  Übungsleiter-Rollen übernehmen kann, wer in die technische Verwaltung darf.
- **Fein, am einzelnen Datensatz:** Eltern sehen ihre Kinder bis zu deren 18. Geburtstag; Übungsleiter sehen
  Teilnehmer nur bei eigenen Terminen und bis 14 Tage danach; wer einen Termin leitet, darf dort Übungsleiter ändern;
  bestätigte Stunden ändert nur, wer sie bestätigt hat.

## Entscheidung

- **Feste Rollen im Code:** `Role` in `portal/accounts/models.py` (Mitglied, Übungsleiter, Abteilungsleiter,
  Administrator). Am Benutzer stehen sie als Liste im Feld `User.roles` (JSON); Einladungen tragen die Rollen ebenso
  mit (`Invitation.roles`). Eltern sind keine Rolle, sondern verknüpfte Benutzer (ADR 0003).
- **Grobe Rechte** prüfen Views mit `role_required(...)` bzw. `user.has_role(...)` gegen benannte Tupel wie
  `MANAGE_USERS`, `MANAGE_MEMBERS` und `MANAGE_EVENTS`.
- **Feine Rechte** stehen als Funktionen in den Services der Fachbereiche (`visible_members`, `can_self_edit`,
  `can_lead`, `can_see_participants`, `locked_reason` …) und sind mit pytest abgedeckt.
- **Vergeben** werden Rollen in der Benutzerverwaltung des Portals: Die Abteilungsleitung vergibt alle außer
  Administrator. `User.set_roles` setzt bei der Rolle Administrator `is_staff` und `is_superuser`; nur Administratoren
  kommen in die technische Verwaltung und haben dort alle Rechte.
- **Django-Gruppen und Einzelberechtigungen bleiben ungenutzt.** Die Felder `groups` und `user_permissions` sind in der
  Benutzer-Maske der technischen Verwaltung ausgeblendet; der Bereich „Gruppen“, den Django selbst anmeldet, bleibt leer.

## Konsequenzen

- ➕ Eine Stelle für alle Rechte, im Code, getestet und im Review sichtbar. Niemand kann Rechte in der Datenbank
  zusammenklicken, ohne dass Tests es abdecken.
- ➕ Der Code hängt nicht von Datensätzen ab: Umbenannte oder gelöschte Gruppen können die Rechteprüfung nicht brechen;
  es braucht keine Datenmigration, die Gruppen anlegt.
- ➕ Einladungen, Benutzerverwaltung und Rechteprüfung arbeiten mit derselben einfachen Liste.
- ➖ Abweichung vom Django-Standard: Wer Django kennt, erwartet Gruppen; der leere Bereich „Gruppen“ in der technischen
  Verwaltung kann verwirren.
- ➖ Eine neue Rolle oder ein geändertes Recht braucht immer eine Code-Änderung und ein Release.
- ➖ Nach Rollen filtern ist mit einem JSON-Feld umständlicher als mit einer m:n-Beziehung (bei der Größe des Vereins
  unkritisch).

## Verworfene Alternativen

- **Django-Gruppen mit Modell-Berechtigungen:** decken nur die groben Rechte ab („darf Mitglieder ändern“), nicht die
  am Datensatz. Die Rechte wären auf Gruppen in der Datenbank und Prüfungen im Code verteilt; der Code müsste trotzdem
  Gruppennamen kennen.
- **django-guardian (Objektrechte in der Datenbank):** müsste jede Verknüpfung und jede Teilnahme als Rechte-Eintrag
  spiegeln und bei jeder Änderung nachziehen (Elternverknüpfung endet mit 18, Übungsleiter wechseln …). Fehleranfällig
  und schwer nachvollziehbar.
- **django-rules (Regeln als Prädikate im Code):** passt zum Ansatz, bringt aber außer einer zweiten Schreibweise
  derselben Funktionen keinen Gewinn und eine weitere Abhängigkeit.
