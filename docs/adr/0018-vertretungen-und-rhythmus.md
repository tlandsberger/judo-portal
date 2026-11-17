# 0018 – Vertretungen und Rhythmus von Zeitplänen

- Status: angenommen
- Datum: 2026-11-17

## Kontext

Die meisten Trainings entstehen aus Zeitplänen mit fest eingeteilten Übungsleitern. Fällt jemand aus, sprechen sich
die Übungsleiter untereinander ab. Im Portal ging das nur umständlich: Die Vertretung musste zusätzlich eingetragen
werden, die abgebende Person sich selbst austragen. Benachrichtigt wurde niemand. Wer übernehmen wollte, konnte sich
nur zusätzlich eintragen. Nachträglich gab es dafür die eigene Seite „Nicht dabei?“ (ADR 0012).

Zeitpläne kannten nur „jede Woche“; Trainings alle zwei Wochen oder am 1. Samstag im Monat ließen sich nicht abbilden.

## Entscheidung

### Vertretungen

Im Abschnitt „Übungsleiter“ eines Termins hat jede Zeile ihre Aktionen. Vor dem Termin und nachträglich gilt dieselbe
Bedienung (`services.hand_over`, `services.withdraw`):

- **Übertragen** (die eigene Zeile oder als Leitung des Termins): Wer abgibt, wählt, wer übernimmt. Die Rolle ist
  vorausgewählt.
- **Vertreten** (fremde Zeile, wenn man die Rolle übernehmen darf und noch nicht eingeteilt ist): Man übernimmt den
  Platz mit dessen Rolle.
- **Austragen** ohne Vertretung, z. B. als Co-Trainer.
- **Mich als … eintragen** wie bisher, zusätzlich zu den Eingeteilten.

Übertragen und Vertreten gelten **sofort**, ohne Annahme: Die Übungsleiter sprechen sich vorher ab, und jede
Änderung steht im Protokoll. Wer nicht selbst gehandelt hat, bekommt eine Push-Benachrichtigung bzw. Mail (Anlass
`hand_over`). Nach dem Termin bekommt die Vertretung stattdessen die Bitte, ihre Stunden zu bestätigen, mit demselben
Schlüssel wie die Abend-Erinnerung. Bestätigte Stunden darf nur die Person selbst durch Übertragen oder Austragen
zurücknehmen; eingereichte Monate sperren alles (ADR 0014).

Würde mit dem Austragen vor dem Termin **kein Trainer** (abrechnungsrelevante Übungsleiter-Rolle) mehr übrig bleiben:

1. Das Portal fragt auf einer eigenen Seite nach und bietet dort auch „Übertragen“ an.
2. Nach dem Austragen bekommt die Abteilungsleitung sofort eine Nachricht. Am Termin wird
   `trainer_missing_since` gesetzt.
3. Zwei Tage vor dem Termin erinnert der Zeitplaner die Abteilungsleitung noch einmal, falls bis dahin niemand mit
   abrechnungsrelevanter Rolle eingeteilt ist (`notices.notify_trainer_missing`, je Termin einmal).

Trägt sich wieder jemand als Trainer ein, wird die Markierung gelöscht.

Die Seite „Nicht dabei?“ entfällt. Erinnerung und „Meine Abrechnung“ führen mit „Nicht dabei?“ zum Abschnitt
„Übungsleiter“ des Termins. „Hat nicht stattgefunden“ steht nach Beginn im Menü „Weitere Aktionen“ anstelle von
„Termin absagen“. Die alte Adresse leitet als Altlast dorthin weiter.

### Rhythmus

Ein Zeitplan hat einen **Rhythmus** (`Schedule.repeat`) mit zwei allgemeinen Optionen:

- **Alle x Wochen** (`interval`, Standard 1): Gezählt wird ab der ersten Woche ab „Gültig ab“. So bleibt der Takt
  gleich, egal wann das Portal Termine nachlegt.
- **Jeden n-ten im Monat** (`week_of_month`: 1.–4. oder letzter): z. B. jeden 1. Samstag.

Vorhandene Zeitpläne stehen auf „alle 1 Woche“. `services.schedule_dates` liefert die Tage, `services.on_schedule`
prüft beim Neuerzeugen, ob ein Termin noch passt. Welches Feld gilt, zeigt `rhythm.js`; ohne JavaScript sind beide
Felder sichtbar und die Auswahl entscheidet.

## Konsequenzen

- Vertretungen brauchen ein, zwei Klicks und erreichen die Betroffenen sofort. Fehlbedienungen lassen sich durch
  erneutes Übertragen korrigieren.
- Jeder, der eine Übungsleiter-Rolle übernehmen darf, kann einen fremden Platz übernehmen. Das ist gewollt; Protokoll
  und Nachricht machen es nachvollziehbar.
- Erinnerungen an fehlende Trainer gibt es nur für Termine, bei denen sich jemand ausgetragen hat. Zeitpläne ohne
  feste Übungsleiter lösen keine aus.

## Verworfene Alternativen

- **Übertragen mit Annahme:** sicherer, aber ein Schritt mehr und offene Anfragen müssten verwaltet werden. Die
  Absprache geschieht ohnehin vorher.
- **Feste Auswahl „jede/alle 2/3/4 Wochen“:** weniger allgemein als „alle x Wochen“.
- **Kalenderregeln nach RFC 5545 (RRULE):** mächtig, aber für die beiden Fälle zu viel Oberfläche und Code.
