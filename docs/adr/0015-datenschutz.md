# 0015 – Datenschutz: Protokoll, Auskunft, Löschfristen

- Status: angenommen
- Datum: 2026-11-16

## Kontext

Das Portal speichert Daten von Mitgliedern, Eltern, Übungsleitern und Gästen. Die DSGVO verlangt Nachvollziehbarkeit,
Auskunft für Betroffene (Art. 15/20) und Löschen, wenn der Zweck entfällt (Art. 17). Bisher wurden nur Gäste und das
Versandprotokoll nach 90 Tagen gelöscht; Mitglieder, Benutzer und Abrechnungen blieben für immer.

## Entscheidung

### Änderungsprotokoll

- Modell `AuditEntry` in `portal.core` (`portal/core/audit.py`), damit jede App protokollieren kann, auch
  `portal.accounts`, ohne andere Apps zu kennen.
  - Zeitpunkt, Handelnder (Benutzer oder „automatisch“), Bereich, Aktion, Beschreibung, bei Änderungen Felder alt → neu.
  - Bezüge als einfache IDs (`member_id`, `user_id`, `guest_id`), keine Fremdschlüssel.
- **Protokolliert wird ausdrücklich** in den Services und Views, die etwas ändern (`audit.log`, `audit.snapshot`,
  `audit.diff`), nicht über Model-Signale: Nur dort ist bekannt, wer handelt. Anmeldewege kommen über die Signale von
  allauth (`portal/accounts/audit_signals.py`).
- **Umfang:**
  - Mitglieder: anlegen, ändern (auch CSV-Import und „Meine Daten“), Zugang geben, Verknüpfung lösen, löschen.
  - Benutzer: Einladungen, Rollen, sperren und entsperren, löschen.
  - Anmeldung und Einstellungen: Passwort gesetzt, geändert, zurückgesetzt; Passkey hinzugefügt oder entfernt;
    E-Mail-Adresse und Telefon geändert; Anmeldung von neuem Gerät; Abmelden; Push-Benachrichtigungen an und aus.
  - Termine: An- und Abmeldung, Warteliste, Nachrücken, Ausnahmen, Team, Stunden, Absagen und Änderungen, Gäste.
  - Abrechnung: Sätze, einreichen, freigeben, zurückgeben.
- **Nicht protokolliert:** Lesezugriffe und jede normale Anmeldung (zu viel Rauschen; neue Geräte reichen als
  Sicherheitsnachweis). Das Umbenennen eines Passkeys meldet allauth nicht; es fehlt deshalb.
- Sichtbar für Abteilungsleitung und Admin (Seite „Protokoll“, „Letzte Änderungen“ am Mitglied); Betroffene sehen
  ihre Einträge in der Auskunft.
- **Aufbewahrung 1 Jahr** (nächtlicher Job). Mit einem Mitglied oder Gast verschwinden auch seine Einträge. Bei
  gelöschten Benutzern wird der Handelnde zu „gelöschter Benutzer“.

### Auskunft

- Unter „Meine Daten“ → „Datenauskunft (Art. 15 DSGVO)“: der eigene Benutzer und alle sichtbaren Mitglieder (eigenes
  Profil, Kinder unter 18) als Seite und als **PDF** (fpdf2 wie bei der Abrechnung; gleich aufgebaute Listen als
  Tabelle). Maschinenlesbar (Art. 20) zusätzlich als JSON.
- Ohne Geheimnisse (kein Passwort-Hash, keine Passkey-Schlüssel). Protokolleinträge zum Benutzer nur über ihn selbst,
  nicht das, was er (z. B. als Abteilungsleitung) bei anderen geändert hat.
- Die Abteilungsleitung lädt dieselbe Auskunft für jedes Mitglied herunter.

### Löschen

- **Nach Austritt:** 3 Monate nach dem Austrittsdatum löscht der nächtliche Job das Mitglied.
  - Am Austrittsdatum (oder beim ersten Lauf danach, wenn der Austritt später eingetragen wird) geht eine Mail an alle
    Zugänge des Mitglieds. Direkt per Mail wie andere Mitteilungen zum Zugang (ADR 0011).
  - Gemerkt in `Member.deletion_notice_sent_at`; ändert sich der Austritt, wird das zurückgesetzt.
  - Die Mitgliederliste zeigt, wer in den nächsten 30 Tagen gelöscht wird.
- **Auf Wunsch:** „Mitglied löschen“ mit Bestätigungsseite, die nennt, was verschwindet.
- **Was gelöscht wird:** Mitglied, Verknüpfungen, Teilnahmen, Abrechnungen mit Zeilen (`Claim.member` jetzt CASCADE;
  die Geschäftsstelle bewahrt die PDFs auf), Stundensätze, Protokolleinträge.
- **Benutzer** ohne verbleibendes Mitglied und ohne Funktionsrolle (Übungsleiter, Abteilungsleitung, Admin; die Rolle
  „Mitglied“ zählt nicht) werden mitgelöscht und per Mail informiert.
- Im Protokoll bleibt „Mitglied Nr. … gelöscht (Grund)“. Die Mitgliedsnummer ist im Portal danach nicht mehr
  auflösbar. Rechtlich ist sie nur pseudonym, da der Hauptverein sie zuordnen kann; als Nachweis der Löschung ist das
  vertretbar und verschwindet nach einem Jahr mit dem Protokoll.
- **Eigener Zugang:** Jeder kann seinen Benutzer selbst löschen (Meine Anmeldung), z. B. wenn ein Kind volljährig
  ist. Die Mitglieder bleiben erhalten und können neu eingeladen werden; nur der letzte Administrator kann es nicht.
- **CSV-Import** legt ausgetretene Mitglieder nie neu an (nur ohne Austritt oder mit Austritt in der Zukunft), damit
  Gelöschte nicht wiederkommen. Bestehende Mitglieder bekommen den Austritt weiterhin.
- Alles in `portal.privacy` (`delete_member`, `run_daily`); keine andere App kennt sie.

### Fristen

| Was | Frist |
|---|---|
| Mitglieder mit allem | 3 Monate nach Austritt |
| Protokoll | 1 Jahr |
| Gäste | 90 Tage nach dem letzten Termin, unbestätigte nach 24 Stunden |
| Versandprotokoll | 90 Tage |
| Sitzungen | Ablauf der Sitzung |
| Backups | Aufbewahrung von restic in der Homecloud |

## Konsequenzen

- Löschen ist endgültig; Backups enthalten die Daten bis zum Ablauf ihrer Aufbewahrung.
- Neue Protokollaufrufe gehören zu jeder neuen Funktion, die personenbezogene Daten ändert (CLAUDE.md).
- Die Abrechnung hängt nicht mehr dauerhaft am Mitglied.

## Verworfene Alternativen

- **django-simple-history / Model-Signale:** protokollieren jedes Speichern, aber ohne den Handelnden zuverlässig und
  mit Kopien aller Felder in eigenen Tabellen; schwer gezielt zu löschen.
- **Pseudonymisieren statt Löschen:** behält Teilnahmen für Statistik, aber ohne Nutzen für die Abteilung und mit
  Restrisiko.
- **Eigene Aufbewahrung der Abrechnungen:** die Geschäftsstelle bewahrt sie auf; doppelte Aufbewahrung braucht es nicht.
