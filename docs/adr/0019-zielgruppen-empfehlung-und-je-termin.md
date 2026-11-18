# 0019 – Zielgruppen als Empfehlung oder Vorgabe, je Termin anpassbar

- Status: angenommen
- Datum: 2026-11-18

## Kontext

Zielgruppen (ADR 0010) waren immer eine harte Vorgabe: Wer nicht passte, konnte sich nicht selbst anmelden. Bei
vielen Trainings ist die Zielgruppe aber nur eine Orientierung („eher für Fortgeschrittene“). Außerdem galten die
Zielgruppen für alle Termine einer Veranstaltung; einzelne Termine (z. B. ein Kata-Training nur für Braungurte)
ließen sich nicht abweichend einschränken.

## Entscheidung

- **Schalter je Veranstaltung** `Event.target_mode`: „Vorgabe“ (`required`, Standard und Verhalten wie bisher) oder
  „Empfehlung“ (`recommended`).
  - **Vorgabe:** Wer nicht passt, bekommt einen festen Hinweis ohne Termin-Platzhalter:
    „Du gehörst leider nicht zur Zielgruppe dieses Termins. Anmeldung nur durch Übungs- oder Abteilungsleiter
    möglich.“ Bei Kindern steht der Vorname statt „Du“. Ausnahmen tragen Übungsleiter und Abteilungsleitung wie
    bisher ein.
  - **Empfehlung:** Jeder kann sich anmelden. Die Teilnahme bekommt `off_target`, die Teilnehmerliste zeigt
    „außerhalb der Zielgruppe“. Die Übungsleiter des Termins bekommen sofort eine Benachrichtigung (Anlass
    `off_target`), ohne Übungsleiter die Abteilungsleitung. Bei externen Teilnehmern geschieht das erst nach der
    Bestätigung per Mail. „Vielleicht“ (Gewicht fehlt) gilt als passend.
- **Zielgruppen je Termin:** eigenes Modell `OccurrenceTargetGroup` mit denselben Kriterien und
  `Occurrence.custom_target_groups`. Weichen sie ab, gelten nur sie (`services.target_groups`,
  `services.match_occurrence`); sonst die der Veranstaltung. Anpassen darf nur die Abteilungsleitung. Beim
  Anpassen werden die Zielgruppen der Veranstaltung kopiert, der Termin gilt als geändert (`is_modified`) und bleibt
  bei Neuerzeugung aus dem Zeitplan erhalten. „Wieder wie die Veranstaltung“ löscht die Kopie.
- Der Modus (Empfehlung/Vorgabe) gilt für die ganze Veranstaltung, auch für Termine mit eigenen Zielgruppen.
- Die Benachrichtigung „Anmeldung offen“ geht weiter nur an passende Mitglieder, auch bei Empfehlung.

## Konsequenzen

- Überall, wo es um einen Termin geht (Termine, Anmeldung, Benachrichtigungen, externe Teilnehmer), zählt
  `match_occurrence`. `match_event` bleibt für „Passende Mitglieder“ an der Veranstaltung.
- Bestehende Veranstaltungen bleiben „Vorgabe“; nichts ändert sich ohne Zutun.
- Änderungen an den Zielgruppen eines Termins stehen im Protokoll.

## Verworfene Alternativen

- **Zwei Ebenen (empfohlen und erlaubt) oder ein Schalter je Zielgruppe:** flexibler, aber schwerer zu verstehen.
- **Nullbarer Fremdschlüssel `occurrence` an `TargetGroup`:** hätte jede Abfrage auf `event.target_groups` um einen
  Filter erweitert und wäre leicht zu vergessen.
- **Zielgruppen je Termin auch durch Übungsleiter:** Ausnahmen für einzelne Mitglieder reichen ihnen; die Gruppe
  festzulegen bleibt bei der Abteilungsleitung.
