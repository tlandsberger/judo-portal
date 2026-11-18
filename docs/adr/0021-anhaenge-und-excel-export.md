# 0021 – Dateianhänge im Datenverzeichnis und Excel-Export

- Status: angenommen
- Datum: 2026-11-18

## Kontext

Zu Lehrgängen und Wettkämpfen gehören Ausschreibungen, Packlisten oder Anfahrtsbeschreibungen. Externe Teilnehmer
sollen manche davon sehen, interne Dateien wie Zimmerlisten aber nicht. Außerdem brauchen Übungsleiter und
Abteilungsleitung die Teilnehmer als Tabelle, z. B. für Meldelisten, Hallenbelegung oder die Abrechnung mit dem
Verband.

## Entscheidung

**Anhänge**
- Modell `EventAttachment` an der Veranstaltung mit Titel, Originalname, Größe und dem Schalter „Für externe
  Teilnehmer sichtbar“ (`public`).
- Dateien liegen im Datenverzeichnis unter `MEDIA_ROOT = /data/uploads/anhaenge/<Veranstaltung>/` mit zufälligem
  Namen. Es gibt **keine** öffentliche `MEDIA_URL`: Ausgeliefert wird nur über Views mit Rechteprüfung
  (`FileResponse`; PDF und Bilder im Browser, der Rest als Download, `nosniff`).
  - Benutzer mit Zugang sehen alle Anhänge, an jedem Termin und auf der Veranstaltung.
  - Externe Teilnehmer sehen nur freigegebene Anhänge und nur, solange die Veranstaltung externe Teilnehmer zulässt:
    auf der Anmeldeseite (Anmeldelink der Veranstaltung) und auf ihrer persönlichen Seite (Token des Gastes).
    Beide nutzen `/extern/<token>/anhaenge/<id>/`.
- Erlaubt sind PDF, JPG, PNG, DOCX, XLSX und ODT bis 10 MB; geprüft werden Endung und Größe. Hochladen, freigeben und
  löschen darf die Abteilungsleitung (`MANAGE_EVENTS`); alles wird protokolliert.
- Die Datei verschwindet mit dem Anhang, auch wenn die ganze Veranstaltung gelöscht wird (`post_delete`).

**Excel-Export** mit **openpyxl** in `portal/events/export.py`:
- **Termin:** Teilnehmerliste wie am Termin, Übungsleiter zuerst, mit Judo-Daten und Notfallkontakt. Darf, wer die
  Teilnehmerliste sehen darf (`can_see_participants`).
- **Veranstaltung:** nur Abteilungsleitung, mit optionalem Zeitraum. Blatt „Teilnahmen“ mit einer Zeile je Teilnahme
  und Blatt „Anwesenheit“ (Personen × Termine, „x“ angemeldet, „W“ Warteliste, Anzahl).
- Die Dateien entstehen im Speicher und werden nicht abgelegt. Jeder Export steht im Protokoll (ADR 0015).

## Konsequenzen

- Das Volume `/data` enthält jetzt neben der Datenbank auch Dateien. Das restic-Backup der Homecloud sichert sie mit;
  das nächtliche SQLite-Backup der App nicht.
- Neue Python-Abhängigkeit `openpyxl`. Keine neuen Umgebungsvariablen.
- Anhänge enthalten in der Regel keine personenbezogenen Daten; wer eine Teilnehmerliste hochlädt, sollte sie nicht
  extern freigeben.

## Verworfene Alternativen

- **Öffentliche `MEDIA_URL` über WhiteNoise oder Traefik:** Jeder mit dem Link käme an die Datei, eine Rechteprüfung
  wäre nicht möglich.
- **Dateien in der Datenbank:** bläht SQLite und die nächtlichen Backups auf.
- **CSV statt Excel:** Umlaute, Datumsformate und mehrere Blätter machen in Excel regelmäßig Ärger.
