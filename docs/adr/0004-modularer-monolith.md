# 0004 – Modularer Monolith mit Spring Modulith

- Status: angenommen
- Datum: 2026-10-09

## Kontext

Die fachlichen Bereiche (Mitglieder, Events, Übungsleiterabrechnung) sind klar getrennt,
hängen aber zusammen. So entstehen Abrechnungen aus durchgeführten Trainings. Der Verein
braucht einen einfachen Betrieb mit einer Instanz und ohne verteiltes System.

## Entscheidung

Das Backend ist **eine deploybare Anwendung**, intern in Module geschnitten und mit
**Spring Modulith** abgesichert:

| Modul | Verantwortung |
|---|---|
| `members` | Mitglieder, Mitgliedschaften, Verknüpfung zu Benutzerkonten, Import |
| `events` | Alle Events (Trainings, Wettkämpfe, Lehrgänge, Vereinsveranstaltungen), Gruppen, Anmeldungen, Anwesenheit |
| `billing` | Übungsleiterabrechnung mit Freigabe-Workflow, Belege, Export |
| `shared` | Security, Fehlerbehandlung, Audit-Log, gemeinsame Value Objects |

Regeln:

- Andere Module dürfen nur die öffentliche API eines Moduls (Package-Root) nutzen, alles
  unter `internal` ist tabu. Ein Modulith-Verifikationstest bricht den Build bei Verstößen.
- Die lose Kopplung zwischen Modulen läuft bevorzugt über **Domain-Events**, z. B.
  `TrainingHeld` (`events`) → `billing` erfasst Stunden.
- Jedes Modul besitzt seine eigenen Tabellen. Fremde Tabellen werden nicht direkt gelesen.

## Konsequenzen

- ➕ Einfacher Betrieb und einfache Transaktionen, trotzdem klare Grenzen.
- ➕ Module lassen sich isoliert testen, die Modulstruktur wird automatisch dokumentiert.
- ➕ Ein späteres Herauslösen eines Moduls als eigener Service ist möglich, aber nicht geplant.
- ➖ Die Disziplin bei Modulgrenzen muss durch den Verifikationstest erzwungen werden.

## Verworfene Alternativen

- **Microservices:** viel zu viel Betriebsaufwand für Vereinsgröße und Team.
- **Klassischer Schichten-Monolith ohne Module:** Es droht eine Vermischung der Fachbereiche,
  die Abrechnungslogik würde sich z. B. in den Event-Code ziehen.
