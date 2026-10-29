# 0008 – Rollen nach Vereinsfunktionen

- Status: angenommen (ersetzt die Rollentabelle aus [0003](0003-keycloak-identity.md))
- Datum: 2026-10-29

## Kontext

ADR 0003 hat Rollen nach einem allgemeinen Vereinsschema festgelegt (Vorstand, Kasse). Die Judo-Abteilung
des Wedeler TSV ist aber anders organisiert: Sie wird von einem Abteilungsleiter geführt, Ämter wie
Kassenwart, Jugendwart oder Sportwart sind derzeit nicht besetzt. Rollen ohne Inhaber erzeugen nur
Pflegeaufwand und ungetestete Rechte.

## Entscheidung

Feste Realm-Rollen in Keycloak, mehrere pro Person möglich (z. B. Abteilungsleiter und Übungsleiter):

| Rolle | Anzeige | Zweck |
|---|---|---|
| `member` | Mitglied | eigene Daten, Events, An-/Abmeldungen |
| `trainer` | Übungsleiter | eigene Gruppen, Anwesenheit, eigene Abrechnungen einreichen |
| `department_head` | Abteilungsleiter | Mitgliederverwaltung, abteilungsweite Events, Freigabe von Abrechnungen |
| `admin` | Administrator | technisch: Konten, Rollenvergabe, Systemeinstellungen, Löschen von Fehleingaben |

Rechte in der Mitgliederverwaltung:

| | Lesen | Anlegen/Ändern | Löschen |
|---|---|---|---|
| `department_head` | ✔ | ✔ | – |
| `admin` | ✔ | – | ✔ |

- Endgültiges Löschen ist nur für Fehleingaben gedacht (wer austritt, bekommt ein Austrittsdatum) und liegt
  deshalb beim (technischen) Administrator. Damit er sieht, was er löscht, darf er Mitglieder lesen.
- Neue Ämter (z. B. Kassenwart, Jugendwart, Sportwart) kommen als neue Rolle mit eigenem ADR hinzu, sobald sie
  besetzt sind und ihre Rechte feststehen.
- Alles andere aus ADR 0003 gilt weiter (Keycloak, PKCE, Autorisierung im Backend).

## Konsequenzen

- ➕ Die Rollen entsprechen den tatsächlichen Funktionen in der Abteilung, jede Rolle ist getestet.
- ➖ Der Abteilungsleiter trägt viel allein: Mitgliederpflege und Freigabe von Abrechnungen. Das
  Vier-Augen-Prinzip bei Abrechnungen wird mit dem Abrechnungs-Feature neu geplant (Schritt 8).
- ➖ Eine neue Rolle erfordert Änderungen in Keycloak, Backend (`Role`), Frontend (Labels, Rechte) und Tests.

## Verworfene Alternativen

- **Alle Ämter vorsorglich anlegen:** Rollen ohne Inhaber und ohne klare Rechte, also toter Code.
- **Vorstand/Kasse beibehalten:** passt nicht zur Organisation der Abteilung.
