# 0010 – Veranstaltungen, Termine und Zielgruppen

- Status: angenommen, teilweise ersetzt durch ADR 0012 (Teilnahme mit Rollen, Arten, Anmeldezeitraum am Termin)
- Datum: 2026-11-15

## Kontext

Trainings, Wettkämpfe, Lehrgänge und Prüfungen sollen ins Portal (`portal.events`, Roadmap Schritt 3).
- Mitglieder bzw. Eltern melden sich an.
- Übungsleiter begleiten Termine als Trainer oder Kotrainer; darauf baut später die Übungsleiterabrechnung auf.
- Jedes Mitglied soll schnell sehen, was für es relevant ist.
- Ein starres Gruppenkonzept (gepflegte Trainingsgruppen) hatten wir in ADR 0009 bewusst zurückgestellt.

## Entscheidung

### Veranstaltung, Zeitplan, Termin

- **Veranstaltung** (`Event`): das „Was“, mit Art (Training, Wettkampf, Lehrgang, Prüfung, Sonstiges), Ort,
  Zielgruppen, Anmelderegeln und Standard-Team.
- **Zeitplan** (`Schedule`): wiederkehrende Zeit, zum Beispiel „Dienstag 17:00–18:30, gültig vom … bis …“.
  - Eine Veranstaltung kann mehrere Zeitpläne haben.
  - Ändern sich die Trainingszeiten, endet der alte Zeitplan, und ein neuer beginnt; die Veranstaltung bleibt.
- **Termin** (`Occurrence`): ein konkretes Datum.
  - Termine aus Zeitplänen werden im Voraus als Datensätze angelegt, für die Gültigkeit, höchstens 12 Monate.
  - Der Horizont rollt beim Aufruf der Termin-Seiten weiter (`ensure_generated`); ein Zeitplaner ist dafür nicht nötig.
  - Einmalige Veranstaltungen und Zusatztermine legt man von Hand an.
- Einzelne Termine können abweichen (Uhrzeit, Ort, Hinweis) oder abgesagt werden; Absagen gehen auch für einen
  Zeitraum (Ferien).
- Ändert sich ein Zeitplan, werden nur zukünftige Termine ohne Anmeldungen, Abweichungen, Absage oder bestätigte
  Begleitung neu erzeugt. Die übrigen bleiben und werden der Abteilungsleitung genannt.

### Zielgruppen statt Gruppenlisten

- Eine **Zielgruppe** (`TargetGroup`) ist eine Regel, die zur Veranstaltung gehört und direkt in deren Formular
  gepflegt wird; eine Bezeichnung („U11“) ist optional. Die Kriterien sind alle optional:
  - Alter von–bis **nach Jahrgang** wie bei den Judo-Altersklassen: Jahr des Termins minus Geburtsjahr
  - Geschlecht
  - Gewicht von–bis
  - Graduierung von–bis; ohne Graduierung zählt ein Mitglied als Anfänger
  - Interessen: mindestens eines muss passen
- Innerhalb einer Zielgruppe gilt UND, zwischen den Zielgruppen einer Veranstaltung ODER. Ohne Zielgruppe passt jeder.
- **Vorlagen** (`TargetGroupTemplate`) für Zielgruppen, die öfter gebraucht werden: im Formular „Als Vorlage
  speichern“ oder auf der Seite „Zielgruppen-Vorlagen“. „Aus Vorlage übernehmen“ **kopiert** die Kriterien in die
  Veranstaltung. Änderungen an der Vorlage wirken nur auf künftige Übernahmen.
  - Begründung (November 2026): Zuerst waren Zielgruppen eigenständige, verknüpfte Objekte. In der Praxis werden sie
    selten wiederverwendet; der Umweg über eine eigene Seite lohnte sich nicht. Eine Kopie hält jede Veranstaltung
    unabhängig, sodass eine geänderte Vorlage nicht unbemerkt laufende Anmeldungen anderer Veranstaltungen ändert.
  - Bestehende Zielgruppen wurden zu Vorlagen; jede Veranstaltung bekam Kopien ihrer bisherigen Zielgruppen.
- Das Ergebnis wird bei jedem Aufruf berechnet. Wer älter wird, eine Prüfung besteht oder sein Gewicht ändert, passt
  automatisch; gepflegte Listen gibt es nicht.
- Fehlt das Gewicht, das eine Zielgruppe verlangt, gilt das Mitglied als „vielleicht passend“: Es darf sich anmelden,
  und die Oberfläche bittet um das Gewicht.
- **Interessen** sind ein Merkmal am Mitglied (`portal.members.Interest`). Die Liste pflegt die Abteilungsleitung, die
  Auswahl treffen Mitglieder und Eltern unter „Meine Daten“. Der CSV-Import kennt die Spalte „Interessen“.
- Alle sehen alle Termine. Passende stehen oben, die übrigen unter „Weitere Veranstaltungen“.
- **Anmelden kann man sich nur, wenn das Mitglied passt.** Ausnahmen tragen Abteilungsleitung oder begleitende
  Übungsleiter ein; diese gelten auch nach dem Anmeldeschluss und über die Höchstzahl hinaus.

### Anmeldung

- Die Anmeldung gilt **je Termin**, auch bei Trainings. Die Seite „Termine“ hat dafür Knöpfe direkt am Termin.
- Der Anmeldezeitraum ist optional:
  - fest (Datum und Uhrzeit, für einmalige Veranstaltungen)
  - relativ zum Termin (Tage vorher öffnen, Stunden vorher schließen)
  - Ohne Angabe ist die Anmeldung sofort offen und schließt mit dem Beginn.
- Abmelden geht bis zum Anmeldeschluss; danach nur über Abteilungsleitung oder Begleiter.
- Mit Höchstzahl gibt es eine **Warteliste**. Wird ein Platz frei, rückt der Erste nach und bekommt eine Mail.
- **Gewicht bei Anmeldung erforderlich** (z. B. Wettkampf):
  - Die Anmeldung fragt das Gewicht ab, vorbelegt aus dem Profil.
  - Es wird an der Anmeldung gespeichert und ins Profil übernommen.
- Bei einer Absage bekommen alle Angemeldeten (bzw. deren Eltern) und das Team eine Mail.
- Eine Anwesenheitserfassung gibt es vorerst nicht.

### Begleitung durch Übungsleiter

- **Standard-Team** an der Veranstaltung (`EventStaff`); neue und kommende Termine übernehmen es.
- **Begleitung je Termin** (`Staffing`) mit Funktion Trainer oder Kotrainer.
  - Übungsleiter tragen sich selbst ein und aus.
  - Begleiter ändern das Team ihres Termins, auch die Funktion anderer.
  - Das Standard-Team pflegen Abteilungsleitung und Übungsleiter.
- Nach dem Termin bestätigt der Übungsleiter seine Begleitung mit Dauer. Bestätigte Begleitungen lassen sich nicht
  mehr löschen; sie sind die Grundlage der Abrechnung.

### Rechte

| Wer | Darf |
|---|---|
| Abteilungsleitung, Administrator | Veranstaltungen, Zeitpläne, Termine, Zielgruppen und Interessen pflegen; alle Teilnehmerlisten |
| Übungsleiter | Standard-Team und Begleitung planen; eigene Termine ändern, absagen und mit Hinweis versehen; Teilnehmerliste und Ausnahmen bei eigenen Terminen |
| Mitglied, Eltern | Termine sehen, eigene Mitglieder an- und abmelden |

- Übungsleiter sehen Mitgliederdaten **nur in der Teilnehmerliste von Terminen, die sie begleiten**, ab der Einteilung
  bis 14 Tage nach dem Termin.
  - Angezeigt werden Name, Jahrgang, Graduierung, Gewicht, Hinweis und ein **Notfallkontakt**: das Telefon des
    Mitglieds und Name und Telefon bzw. E-Mail der Eltern.
  - Für Ausnahmen gibt es eine Namenssuche, die nur Name und Jahrgang zeigt.
  - Eine Mitgliederliste bekommen sie weiterhin nicht (ADR 0009).
- Dafür hat der Benutzer jetzt ein optionales Telefon, das jeder unter „Meine Anmeldung“ pflegt.

## Konsequenzen

- Die Termine liegen als Datensätze vor. Anmeldungen, Absagen und Begleitung hängen am einzelnen Termin, und die
  Abrechnung kann direkt darauf aufsetzen.
- Ein Jahr Trainings sind wenige hundert Datensätze, für SQLite unproblematisch.
- Zielgruppen ersetzen die zurückgestellten Trainingsgruppen. Ob es zusätzlich feste Gruppen braucht (z. B.
  nominierter Kader), zeigt die Praxis; eine Ausnahme pro Termin deckt Einzelfälle ab.
- Mitglieder sind für `portal.events` nur über `portal.members.services` erreichbar (eigene Mitglieder, Eltern).

## Verworfene Alternativen

- **Termine nur aus der Regel berechnen** (ohne Datensätze): Absagen, Abweichungen und Anmeldungen bräuchten
  Ausnahmelisten, die Abrechnung bräuchte trotzdem konkrete Termine.
- **Gepflegte Gruppenlisten:** viel Pflege, veraltet schnell; Alter und Graduierung ändern sich ohnehin.
- **Dauer-Anmeldung für Trainingsserien:** weniger Klicks, aber die Planung pro Termin war gewünscht.
- **RFC-5545-Wiederholungsregeln** (RRULE): mächtiger als nötig; Wochentag, Uhrzeit und Zeitraum reichen.
