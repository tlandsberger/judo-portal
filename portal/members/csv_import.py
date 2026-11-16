"""CSV-Import der Mitglieder: erst Vorschau, dann Übernehmen. Abgleich über die Mitgliedsnummer (ADR 0009).

Regeln:
- Pflichtspalten: Mitgliedsnummer, Vorname, Nachname, Geburtsdatum. Weitere Spalten sind optional.
- Leere Zellen überschreiben nichts (z. B. selbst gepflegtes Gewicht bleibt bei einem Export ohne Gewicht erhalten).
- Mitglieder, die nicht in der Datei stehen, bleiben unverändert; der Import löscht nie.
- Unbekannte Spalten werden ignoriert.
- Interessen kommagetrennt mit den Namen aus der Liste im Portal; sie ersetzen die bisherigen Interessen.
"""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from .models import Gender, Grade, Interest, Member

MAX_BYTES = 1_000_000

# Spaltenname in der Datei → Feld. Die Vorlage nutzt die ersten Namen; Groß-/Kleinschreibung ist egal.
COLUMNS: dict[str, tuple[str, ...]] = {
    "member_number": ("Mitgliedsnummer", "Mitgliedsnr", "Mitglieds-Nr", "Nr"),
    "first_name": ("Vorname",),
    "last_name": ("Nachname", "Name"),
    "birth_date": ("Geburtsdatum", "Geboren"),
    "gender": ("Geschlecht",),
    "joined_on": ("Eintritt", "Eintrittsdatum"),
    "left_on": ("Austritt", "Austrittsdatum"),
    "email": ("E-Mail", "Email", "Mail"),
    "phone": ("Telefon", "Mobil", "Handy"),
    "grade": ("Graduierung", "Gürtel"),
    "weight": ("Gewicht",),
    "interests": ("Interessen",),
}
REQUIRED = ("member_number", "first_name", "last_name", "birth_date")
TEMPLATE_HEADER = [names[0] for names in COLUMNS.values()]
TEMPLATE_EXAMPLE = ["1001", "Mia", "Muster", "14.03.2015", "w", "01.09.2021", "", "", "", "6. Kyu", "32,5", ""]

LABELS = {
    "member_number": "Mitgliedsnummer",
    "first_name": "Vorname",
    "last_name": "Nachname",
    "birth_date": "Geburtsdatum",
    "gender": "Geschlecht",
    "joined_on": "Eintritt",
    "left_on": "Austritt",
    "email": "E-Mail",
    "phone": "Telefon",
    "grade": "Graduierung",
    "weight": "Gewicht",
    "interests": "Interessen",
}


class CsvError(Exception):
    """Die Datei als Ganzes ist nicht lesbar (Kodierung, fehlende Pflichtspalten …)."""


@dataclass
class Row:
    line: int
    values: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    member: Member | None = None
    changes: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.errors:
            return "error"
        if self.member is None:
            left_on = self.values.get("left_on")
            # Ausgetretene legt der Import nie neu an (ADR 0015); nur ein Austritt in der Zukunft ist erlaubt.
            return "left" if left_on and left_on <= timezone.localdate() else "new"
        return "changed" if self.changes else "unchanged"

    @property
    def name(self) -> str:
        return f"{self.values.get('first_name', '')} {self.values.get('last_name', '')}".strip()


@dataclass
class Preview:
    rows: list[Row]

    def count(self, status: str) -> int:
        return sum(1 for row in self.rows if row.status == status)

    @property
    def counts(self) -> dict[str, int]:
        return {status: self.count(status) for status in ("new", "changed", "unchanged", "left", "error")}

    @property
    def has_changes(self) -> bool:
        return any(row.status in ("new", "changed") for row in self.rows)


def decode(data: bytes) -> str:
    if len(data) > MAX_BYTES:
        raise CsvError("Die Datei ist zu groß (höchstens 1 MB).")
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise CsvError("Die Datei ist nicht lesbar. Speichere sie bitte als CSV (UTF-8).")


def preview(text: str) -> Preview:
    reader = _reader(text)
    columns = _map_columns(reader.fieldnames or [])
    rows: list[Row] = []
    seen: dict[str, int] = {}
    for line, raw in enumerate(reader, start=2):
        cells = {key: (raw.get(column) or "").strip() for key, column in columns.items()}
        if not any(cells.values()):
            continue
        row = _parse(line, cells)
        number = row.values.get("member_number")
        if number:
            if number in seen:
                row.errors.append(f"Mitgliedsnummer {number} steht schon in Zeile {seen[number]}.")
            seen.setdefault(number, line)
        if not row.errors:
            row.member = Member.objects.filter(member_number=number).first()
            row.changes = _changes(row.member, row.values) if row.member else []
        rows.append(row)
    return Preview(rows=rows)


@transaction.atomic
def apply(text: str, by: Any = None) -> Preview:
    """Übernimmt alle fehlerfreien Zeilen. Wird neu aus dem Text berechnet, nicht aus einer alten Vorschau."""
    from . import services

    result = preview(text)
    for row in result.rows:
        if row.status not in ("new", "changed"):
            continue
        member = row.member or Member()
        before = services.member_snapshot(row.member)
        interests = row.values.get("interests")
        for key, value in row.values.items():
            if key != "interests":
                setattr(member, key, value)
        member.full_clean()
        member.save()
        if interests is not None:
            member.interests.set(interests)
        services.record_change(member, before, by, "CSV-Import")
    return result


def template_csv() -> str:
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";", lineterminator="\r\n")
    writer.writerow(TEMPLATE_HEADER)
    writer.writerow(TEMPLATE_EXAMPLE)
    return "﻿" + out.getvalue()


def _reader(text: str) -> csv.DictReader[str]:
    first_line = text.lstrip("﻿").split("\n", 1)[0]
    delimiter = max(";,\t", key=first_line.count)
    return csv.DictReader(io.StringIO(text.lstrip("﻿")), delimiter=delimiter)


def _map_columns(header: Sequence[str]) -> dict[str, str]:
    normalized = {_norm(name): name for name in header if name}
    columns = {}
    for key, names in COLUMNS.items():
        for name in names:
            if _norm(name) in normalized:
                columns[key] = normalized[_norm(name)]
                break
    missing = [LABELS[key] for key in REQUIRED if key not in columns]
    if missing:
        raise CsvError(f"Es fehlen Spalten: {', '.join(missing)}. Nutze am besten die Vorlage.")
    return columns


def _norm(name: str) -> str:
    return re.sub(r"[\s._-]", "", name).casefold()


def _parse(line: int, cells: dict[str, str]) -> Row:
    row = Row(line=line)
    for key, raw in cells.items():
        if not raw:
            if key in REQUIRED:
                row.errors.append(f"{LABELS[key]} fehlt.")
            continue
        try:
            row.values[key] = PARSERS.get(key, _text)(raw)
        except ValueError as error:
            row.errors.append(f"{LABELS[key]}: {error}")
    return row


def _text(raw: str) -> str:
    return raw[:100]


def _date(raw: str) -> date:
    for pattern in ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y"):
        try:
            return datetime.strptime(raw, pattern).date()
        except ValueError:
            continue
    raise ValueError(f"„{raw}“ ist kein Datum (TT.MM.JJJJ).")


def _gender(raw: str) -> str:
    value = raw.strip().lower()[:1]
    if value == "f":
        value = "w"
    if value not in Gender.values:
        raise ValueError(f"„{raw}“ ist unbekannt (w, m oder d).")
    return value


def _grade(raw: str) -> str:
    match = re.fullmatch(r"(\d{1,2})\s*\.?\s*(kyu|dan)", raw.strip(), re.IGNORECASE)
    value = f"{match.group(2).lower()}{int(match.group(1))}" if match else ""
    if value not in Grade.values:
        raise ValueError(f"„{raw}“ ist unbekannt (z. B. 5. Kyu oder 1. Dan).")
    return value


def _weight(raw: str) -> Decimal:
    try:
        value = Decimal(raw.replace("kg", "").strip().replace(",", ".")).quantize(Decimal("0.1"))
    except InvalidOperation:
        raise ValueError(f"„{raw}“ ist keine Zahl.") from None
    if not Decimal("10") <= value <= Decimal("250"):
        raise ValueError(f"{raw} kg liegt nicht zwischen 10 und 250.")
    return value


def _email(raw: str) -> str:
    try:
        validate_email(raw)
    except ValidationError:
        raise ValueError(f"„{raw}“ ist keine gültige Adresse.") from None
    return raw.lower()


def _interests(raw: str) -> list[Interest]:
    names = [name.strip() for name in re.split(r"[,|]", raw) if name.strip()]
    known = {interest.name.casefold(): interest for interest in Interest.objects.all()}
    unknown = [name for name in names if name.casefold() not in known]
    if unknown:
        raise ValueError(f"unbekannt: {', '.join(unknown)} (Liste unter Mitglieder → Interessen).")
    return sorted({known[name.casefold()] for name in names}, key=lambda interest: interest.pk)


PARSERS = {
    "birth_date": _date,
    "joined_on": _date,
    "left_on": _date,
    "gender": _gender,
    "grade": _grade,
    "weight": _weight,
    "email": _email,
    "interests": _interests,
}


def _changes(member: Member, values: dict[str, Any]) -> list[str]:
    changes = []
    for key, value in values.items():
        if key == "interests":
            if set(member.interests.all()) != set(value):
                changes.append(LABELS[key])
        elif getattr(member, key) != value:
            changes.append(LABELS[key])
    return changes
