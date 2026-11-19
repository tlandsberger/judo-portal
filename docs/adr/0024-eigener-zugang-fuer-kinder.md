# 0024 – Eigener Zugang für Kinder ab 14, eingerichtet von den Eltern

- Status: angenommen
- Datum: 2026-11-19
- Ergänzt: [0009](0009-mitgliederdaten-und-csv-import.md) (Zugänge für Mitglieder und Eltern)

## Kontext

Ab 14 kann ein Mitglied einen eigenen Zugang bekommen, bisher nur über die Abteilungsleitung. Die Eltern kennen die
Adresse ihres Kindes und wissen, wann es so weit ist. Sie sollen den Zugang selbst anstoßen können. Zum 14. Geburtstag
sollen sie per Mail und auf der Startseite darauf hingewiesen werden.

## Entscheidung

- **Normale Einladung:** Eltern geben nur die Adresse des Kindes ein. `child_access.invite_child` nutzt
  `services.give_access` mit „Eigenes Profil“. Es entsteht also dieselbe Einladung mit offener Verknüpfung wie bei der
  Abteilungsleitung; das Kind richtet seine Anmeldewege selbst ein. Eine frühere offene Einladung für den eigenen
  Zugang des Kindes wird ersetzt.
- **Keine Verknüpfung mit bestehenden Benutzern:** Anders als die Abteilungsleitung dürfen Eltern keine Adresse
  angeben, zu der es schon einen Benutzer gibt (auch nicht die eigene). Sonst könnten sie einen fremden Benutzer mit
  ihrem Kind verknüpfen. Solche Fälle klärt die Abteilungsleitung.
- **Wer darf:** Benutzer mit gültiger Verknüpfung „Erziehungsberechtigt“, solange das Kind 14 bis 17 ist, aktiv ist
  und noch keinen eigenen Zugang hat.
- **Hinweise:** Neues Modell `AccessOffer` je Elternteil und Kind. Es hält fest, ob die Mail raus ist und ob das
  Banner mit „Nicht jetzt“ ausgeblendet wurde. Das Banner steht, solange das Kind keinen Zugang und keine offene
  Einladung hat. Die Mail geht direkt raus (Zugänge laufen immer per Mail, ADR 0011), einmal je Elternteil, aus einem
  nächtlichen Job. Er holt verpasste Mails bis zu 7 Tage nach dem Geburtstag nach. Kinder, die beim Start schon länger
  14 sind, bekommen also nur das Banner.
- **Mitgliedsdaten:** Mit dem vorausgewählten Häkchen wird die Adresse in die Mitgliedsdaten des Kindes übernommen
  (protokolliert). Einladung und Übernahme stehen im Protokoll; die Abteilungsleitung bekommt keine eigene
  Benachrichtigung.
- **Datenschutz:** Die Hinweise gehören zur Auskunft des Elternteils und fallen mit Benutzer oder Mitglied weg.

## Konsequenzen

- ➕ Weniger Arbeit für die Abteilungsleitung; Jugendliche kommen früher zu einem eigenen Zugang.
- ➕ Kein neuer Einladungsweg: Ablauf, Fristen und Mails sind dieselben.
- ➖ Ein kleines Modell nur für die Hinweise.

## Verworfene Alternativen

- **Hinweise ohne Modell (nur aus dem Alter berechnet):** Dann ließe sich weder „Nicht jetzt“ merken noch
  verhindern, dass die Mail doppelt rausgeht.
- **Hinweis über `notify` (Push-Benachrichtigung):** Es geht um einen Zugang. Solche Hinweise gehen nach ADR 0011
  immer per Mail.
