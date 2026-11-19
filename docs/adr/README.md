# Architekturentscheidungen (ADRs)

Mit dem Neuaufbau im November 2026 beginnt die Nummerierung neu; die ADRs der Vorgängerversion
(Spring Boot/Angular/Keycloak) stehen in der Git-Historie.

| Nr. | Titel | Status |
|---|---|---|
| [0001](0001-django-mit-serverseitigem-rendering.md) | Django mit serverseitigem Rendering und htmx | angenommen |
| [0002](0002-anmeldung-in-der-app.md) | Anmeldung in der App mit django-allauth (Passkey, Passwort, Mail-Code) | angenommen |
| [0003](0003-benutzer-und-mitglieder-getrennt.md) | Benutzer und Mitglieder getrennt, Verknüpfungen m:n | angenommen |
| [0004](0004-sqlite.md) | SQLite statt Datenbankserver | angenommen |
| [0005](0005-bootstrap-mit-wtsv-theme.md) | Bootstrap 5.3 mit WTSV-Theme | ersetzt durch 0008 |
| [0006](0006-automatisierte-wartung-und-releases.md) | Automatisierte Wartung und wöchentliche Releases | angenommen |
| [0007](0007-betrieb-in-der-homecloud.md) | Betrieb als ein Container in der Homecloud | angenommen |
| [0008](0008-tailwind-und-daisyui.md) | Tailwind CSS und DaisyUI statt Bootstrap | angenommen |
| [0009](0009-mitgliederdaten-und-csv-import.md) | Mitgliederdaten, Zugänge und CSV-Import | angenommen |
| [0010](0010-veranstaltungen-termine-und-zielgruppen.md) | Veranstaltungen, Termine und Zielgruppen | angenommen |
| [0011](0011-push-benachrichtigungen.md) | Push-Benachrichtigungen mit Mail als Ersatz | angenommen |
| [0012](0012-teilnahme-mit-rollen.md) | Teilnahme mit Rollen | angenommen |
| [0013](0013-gaeste.md) | Gäste | angenommen |
| [0014](0014-uebungsleiterabrechnung.md) | Übungsleiterabrechnung | angenommen |
| [0015](0015-datenschutz.md) | Datenschutz: Protokoll, Auskunft, Löschfristen | angenommen |
| [0016](0016-hilfe-im-portal.md) | Hilfe im Portal | angenommen |
| [0017](0017-einheitliche-bedienung.md) | Einheitliche Bedienung: Listen, Detailseiten und Schaltflächen | angenommen |
| [0018](0018-vertretungen-und-rhythmus.md) | Vertretungen und Rhythmus von Zeitplänen | angenommen |
| [0019](0019-zielgruppen-empfehlung-und-je-termin.md) | Zielgruppen als Empfehlung oder Vorgabe, je Termin | angenommen |
| [0020](0020-schnellzugang-per-code-und-qr-code.md) | Schnellzugang per Code, Quick-Link und QR-Code | angenommen |
| [0021](0021-anhaenge-und-excel-export.md) | Dateianhänge im Datenverzeichnis und Excel-Export | angenommen |
| [0022](0022-feste-rollen-statt-django-gruppen.md) | Feste Rollen statt Django-Gruppen und -Berechtigungen | angenommen |
| [0023](0023-e-mail-adresse-aendern.md) | E-Mail-Adresse ändern mit Bestätigung | angenommen |

Vorlage: Kontext · Entscheidung · Konsequenzen · Verworfene Alternativen.
