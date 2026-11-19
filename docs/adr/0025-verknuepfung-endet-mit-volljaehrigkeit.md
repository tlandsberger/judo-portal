# 0025 – Verknüpfung der Eltern endet mit der Volljährigkeit

- Status: angenommen
- Datum: 2026-11-19
- Ergänzt: [0009](0009-mitgliederdaten-und-csv-import.md), [0015](0015-datenschutz.md), [0024](0024-eigener-zugang-fuer-kinder.md)

## Kontext

Die Verknüpfung „Erziehungsberechtigt“ wirkt nur bis zum 18. Geburtstag (`MemberLink.is_effective`), blieb aber
gespeichert. Eltern behielten so einen Zugang ohne Zweck, und die Daten lagen länger als nötig. Ab 18 sollen die
Verknüpfung gelöst und ein Zugang ohne weiteres Mitglied gelöscht werden. Die Eltern sollen einen Monat vorher davon
erfahren und über beides per Mail informiert werden.

## Entscheidung

- **Nächtlicher Job in `portal.privacy`** (neben dem Löschen nach dem Austritt):
  - `send_adult_notices`: Einen Monat vor dem 18. Geburtstag (`Member.adult_on`, am 29. Februar Geborene am
    1. März) geht eine Vorankündigung an jeden verknüpften Elternteil, einmal je Verknüpfung
    (`MemberLink.adult_notice_sent_at`). Sie sagt, ob der Zugang danach gelöscht wird. Hat das Kind noch keinen
    eigenen Zugang, enthält sie den Link „Zugang einrichten“ (ADR 0024). Wird eine Verknüpfung erst kurz vor dem
    Geburtstag angelegt, kommt die Mail entsprechend später.
  - `release_adult_children`: Ab dem 18. Geburtstag wird die Verknüpfung gelöscht, auch ohne vorherige Ankündigung.
- **Zugang löschen nach derselben Regel wie beim Austritt** (`_keeps_access`): Der Zugang bleibt, wenn der Benutzer
  noch ein Mitglied hat (auch vorgemerkt aus einer Einladung) oder eine Funktionsrolle (Übungsleiter,
  Abteilungsleitung, Administrator).
- **Eine Mail für beides:** „Verknüpfung gelöst“ beziehungsweise „Verknüpfung gelöst und Zugang gelöscht“. Die
  allgemeine Mail „Dein Zugang wurde gelöscht“ entfällt dann (`delete_user(..., notify=False)`).
- **Protokoll:** Vorankündigung und Lösen stehen im Protokoll des Mitglieds. Wird der Zugang gelöscht, fällt sein
  Protokoll mit ihm weg (ADR 0015).

## Konsequenzen

- ➕ Keine verwaisten Zugänge, Daten nur so lange wie nötig.
- ➕ Eltern werden rechtzeitig informiert und können den eigenen Zugang des Kindes noch einrichten.
- ➖ Wer die Verknüpfung über 18 hinaus braucht (z. B. als Betreuer), muss von der Abteilungsleitung neu verknüpft
  werden. Das gibt es heute nicht als Art der Verknüpfung.

## Verworfene Alternativen

- **Verknüpfung behalten und nur ausblenden (bisher):** Der Zugang bleibt ohne Zweck bestehen, und die Daten bleiben
  länger als nötig.
- **Zwei Mails (gelöst, gelöscht):** Sie kommen zur selben Zeit und sagen zusammen dasselbe wie eine Mail.
