# 0012 – Teilnahme mit Rollen

- Status: angenommen
- Datum: 2026-11-16
- Ergänzt ADR 0010 und ersetzt dort Anmeldung und Begleitung als getrennte Modelle sowie die festen Arten.
- Begriff (November 2026): In Oberfläche, Hilfe und Doku heißt das „Team“ inzwischen **„Übungsleiter“**, das
  Standard-Team „feste Übungsleiter“. Im Code und in diesem ADR bleibt `team`.

## Kontext

Nach dem ersten Release der Veranstaltungen (ADR 0010) zeigten sich drei Schwächen:

- **Doppelte Rolle:** Übungsleiter konnten einen Termin begleiten und gleichzeitig als Teilnehmer angemeldet sein.
- **Falsches Modell:** Teilnehmer waren Mitglieder, das Team aber Benutzer. Tatsächlich sind Übungsleiter und
  Abteilungsleiter selbst Mitglieder der Abteilung.
- **Zu starr:** Arten (Training, Wettkampf …) und Funktionen (Trainer, Kotrainer) waren fest im Code. Prüfer und
  Betreuer fehlten.
- **Falscher Ort:** Der Anmeldezeitraum hing an der Veranstaltung, gehört aber zum einzelnen Termin.

## Entscheidung

### Eine Teilnahme je Person und Termin

- `Participation` ersetzt `Registration` und `Staffing`: Termin, Mitglied, **Rolle**, Status, Gewicht, Hinweis,
  bestätigte Minuten. Eindeutig je Termin und Mitglied.
- Wer als Trainer eingetragen ist, ist damit nicht zusätzlich Teilnehmer. Wird ein angemeldetes Mitglied ins Team
  geholt, wird seine Teilnahme umgestellt; ein frei gewordener Platz geht an die Warteliste.

### Rollen und Arten pflegt die Abteilungsleitung

- **Veranstaltungsarten** (`EventType`): Name, Reihenfolge, aktiv. Benutzte Arten lassen sich nur deaktivieren.
- **Rollen** (`ParticipantRole`):

  | Feld | Bedeutung |
  |---|---|
  | Veranstaltungsarten | Bei welchen Arten die Rolle angeboten wird; leer heißt bei allen |
  | Benutzerrollen | Wer sie übernehmen darf (über den eigenen Zugang des Mitglieds); leer heißt jedes Mitglied |
  | Team | Zählt nicht zur Höchstzahl, sieht die Teilnehmerliste eigener Termine, darf den Termin leiten |
  | Abrechnungsrelevant | Stunden werden nach dem Termin bestätigt; Grundlage der Übungsleiterabrechnung |
  | Rolle bei Anmeldung | Genau eine Rolle; die bekommt, wer sich anmeldet oder angemeldet wird |

- **Startwerte** (Migration):

  | Rolle | Arten | Benutzerrollen | Team | Abrechnungsrelevant |
  |---|---|---|---|---|
  | Teilnehmer (bei Anmeldung) | alle | alle Mitglieder | nein | nein |
  | Trainer | Training, Lehrgang | Übungsleiter | ja | ja |
  | Co-Trainer | Training, Lehrgang | Übungsleiter | ja | ja |
  | Prüfer | Prüfung | Übungsleiter | ja | nein |
  | Betreuer | Wettkampf, Lehrgang | Übungsleiter | ja | nein |

- **Team-Rollen** brauchen ein eigenes Mitgliedsprofil (Verknüpfung „eigenes Profil“), dessen Benutzer eine der
  Benutzerrollen hat (`services.can_take_role`). Die Seite „Rollen“ nennt Übungsleiter ohne eigenes Profil.
- **Rechte:** Den Termin leitet, wer eine Team-Rolle daran hat (`can_lead`), dazu die Abteilungsleitung.

### Standard-Team am Zeitplan

- `ScheduleTeam` (Zeitplan, Mitglied, Rolle) statt `EventStaff` an der Veranstaltung. Trainingszeiten und Teams ändern
  sich oft zusammen: Ein neuer Zeitplan ab Januar bekommt sein eigenes Team.
- Zukünftige Termine des Zeitplans ziehen bei Änderungen nach; bestätigte Stunden bleiben.
- Einzeltermine bekommen ihr Team direkt am Termin. Nach „Termin anlegen“ öffnet sich deshalb der Termin.

### Anmeldezeitraum am Termin

- `Occurrence.registration_opens_at` und `registration_closes_at`, leer heißt sofort bzw. bis zum Beginn.
- Der Zeitplan hat die Regel „öffnet X Stunden vorher“ und „schließt Y Stunden vorher“. Beim Erzeugen und bei
  Änderungen rechnet das Portal die Zeiten der zukünftigen Termine aus, außer bei Terminen mit eigener Abweichung.
- „Anmeldung offen“ und die Erinnerung zum Anmeldeschluss gehen nur für Einzeltermine raus (ohne Zeitplan), nicht mehr
  über die Art „Training“.

### Anlegen mit Terminen

- „Veranstaltung anlegen“ fragt gleich nach den Terminen: **einmalig** (ein Termin mit Anmeldezeitraum),
  **wiederkehrend** (Wochentage, Uhrzeit, Gültigkeit, Regel für den Anmeldezeitraum; je Wochentag ein Zeitplan) oder
  **später**. Optional ein Team (Mitglied und Rolle): bei „wiederkehrend“ das Standard-Team der Zeitpläne.
- `services.create_event` legt alles atomar an. Passt die Rolle nicht zur Art, wird nichts gespeichert.
- `static/js/event-form.js` blendet die Felder der gewählten Variante ein; ohne JavaScript sind alle sichtbar.

### Termine ohne Doppelungen

- „Termine“ und die Startseite zeigen jeden Termin einmal. Darunter stehen die eigenen Mitglieder, für die er passt
  oder die eingetragen sind, mit Status (auch Team-Rolle) und eigenem Knopf (`services.agenda` → `AgendaEntry`).
- Mit nur einem eigenen Mitglied stehen Status und Knopf direkt in der Terminzeile.
- Termine, die zu keinem eigenen Mitglied passen, stehen zugeklappt unter „Weitere Veranstaltungen“.

### Begriffe

- „Co-Trainer“ statt „Kotrainer“.
- „Stunden“ statt „Begleitung“ oder „Einsatz“: „Stunden bestätigen“, Seite „Meine Stunden“ (`/stunden/`).
- Eine Bestätigung lässt sich zurücknehmen (z. B. versehentlich bestätigt), solange der Monat nicht zur Abrechnung eingereicht ist.
- **Nicht dabei?** Nachträglich (ab Beginn des Termins) kann sich ein Team-Mitglied austragen, an eine Vertretung
  übertragen (die Vertretung wird eingetragen und bekommt die Erinnerung zum Bestätigen) oder den Termin nachträglich
  absagen (ohne Nachrichten an Teilnehmer; nicht, wenn jemand anderes schon bestätigt hat). Die Erinnerung „Stunden
  bestätigen“ hat dafür einen zweiten Knopf, der die Seite öffnet. Alles respektiert die Sperre durch die Abrechnung.
  Seit ADR 0018 steht das direkt am Termin (Übertragen, Vertreten, Austragen), vor und nach Beginn.

## Konsequenzen

- **Migration:** Anmeldungen werden Teilnahmen mit der Rolle Teilnehmer, Begleitungen Teilnahmen des eigenen
  Mitglieds des Übungsleiters. Begleitungen von Übungsleitern ohne eigenes Mitgliedsprofil werden übersprungen und im
  Migrationslog genannt. Das Standard-Team der Veranstaltung geht an alle ihre Zeitpläne; „Tage vorher“ wird zu
  Stunden.
- **Knöpfe an Push-Benachrichtigungen:** Die Tokens tragen jetzt die Teilnahme (`p`). Knöpfe aus Nachrichten vor dem Update führen ins
  Portal statt die Aktion auszuführen.
- Übungsleiter brauchen ein eigenes Mitgliedsprofil, um ins Team zu kommen.

## Verworfene Alternativen

- **Team weiter als Benutzer:** Ein externer Prüfer bräuchte so keinen Mitgliedsdatensatz. Er hätte aber auch keinen
  Zugang zum Portal, und die doppelte Rolle (Teilnehmer und Trainer) ließe sich nicht verhindern.
- **Feste Rollen im Code:** einfacher, aber jede neue Rolle (z. B. Kampfrichter) bräuchte ein Release.
