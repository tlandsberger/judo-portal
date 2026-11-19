# 0023 – E-Mail-Adresse ändern mit Bestätigung

- Status: angenommen
- Datum: 2026-11-19
- Ergänzt: [0002](0002-anmeldung-in-der-app.md), [0011](0011-push-benachrichtigungen.md) (Sicherheitsmails)

## Kontext

Die E-Mail-Adresse ist der Benutzername für die Anmeldung, an sie gehen Anmeldecodes, Einladungen und
Sicherheitsmails. Bisher ließ sie sich nur in der technischen Verwaltung ändern. Benutzer sollen sie selbst ändern
können, die Abteilungsleitung für andere (z. B. wenn die alte Adresse nicht mehr erreichbar ist). Wer ein eigenes
Mitgliedsprofil hat, soll die neue Adresse dort gleich mit übernehmen können.

## Entscheidung

- **Erst bestätigen, dann gilt sie:** Die neue Adresse wird als `EmailChange` (je Benutzer höchstens eine, 3 Tage
  gültig) vorgemerkt; an sie geht ein Link. Bestätigt wird per Klick (POST), ein bloßes Öffnen des Links ändert
  nichts. Danach setzt `services.confirm_email_change` `User.email` und den Eintrag in allauths `EmailAddress`
  (bestätigt, primär) und löscht die Vormerkung.
- **Hinweis an die alte Adresse** über die Sicherheitsmails von allauth (`account/email/email_changed`), wie bei
  Passwort und neuem Gerät.
- **Eigene Umsetzung statt allauths E-Mail-Verwaltung:** allauth verwaltet mehrere Adressen je Benutzer und kennt
  keine Änderung im Auftrag der Abteilungsleitung. Bei uns hat jeder genau eine Adresse
  (`ACCOUNT_EMAIL_VERIFICATION = "none"`, Adressen sind durch die Einladung bestätigt).
- **Mitgliedsdaten:** `portal.accounts` kennt die Mitglieder nicht. Über das Signal `own_member_requested` fragt es
  nach dem eigenen Profil (für das Häkchen „Auch in meine Mitgliedsdaten übernehmen“, vorausgewählt), über
  `email_changed` übernimmt `portal.members` die Adresse nach der Bestätigung (protokolliert wie andere Änderungen).
- **Protokoll und Auskunft:** Anfrage, Verwerfen und Änderung stehen im Protokoll (`audit.log`); eine offene
  Änderung gehört zur Datenauskunft und fällt mit dem Benutzer weg.

## Konsequenzen

- ➕ Kein Aussperren durch Tippfehler; eine Übernahme des Zugangs fällt durch den Hinweis an die alte Adresse auf.
- ➕ Die Abteilungsleitung kann helfen, ohne die technische Verwaltung zu brauchen; wirksam wird es trotzdem nur mit
  Zugriff auf die neue Adresse.
- ➖ Ein eigenes kleines Modell und ein eigener Mail-Ablauf neben allauth.

## Verworfene Alternativen

- **Sofort ändern, nur Hinweis an die alte Adresse:** einfacher, aber ein Tippfehler sperrt aus (der Anmeldecode
  ginge an eine falsche Adresse).
- **allauth `ACCOUNT_CHANGE_EMAIL`:** setzt auf allauths E-Mail-Verwaltung mit Bestätigungspflicht für alle Adressen
  und kennt keine Änderung durch Dritte.
