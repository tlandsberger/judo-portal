"""Excel-Export der Teilnehmer (ADR 0021): Teilnehmerliste eines Termins und Übersicht einer Veranstaltung.

Die Exporte enthalten personenbezogene Daten; die Views protokollieren jeden Export (ADR 0015).
"""

from __future__ import annotations

from datetime import date
from io import BytesIO
from typing import Any

from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from portal.members import services as members

from .models import Event, Occurrence, Participation, ParticipationStatus
from .services import ACTIVE, age_in_year

CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

PARTICIPANT_COLUMNS = [
    "Nachname",
    "Vorname",
    "Rolle",
    "Status",
    "Jahrgang",
    "Alter",
    "Geschlecht",
    "Graduierung",
    "Gewicht (kg)",
    "Verein",
    "Hinweis",
    "Besonderheit",
    "Telefon",
    "Erziehungsberechtigte",
]


def _sheet(workbook: Workbook, title: str, header: list[str], first: bool = False) -> Worksheet:
    sheet: Worksheet = workbook.active if first else workbook.create_sheet()
    sheet.title = title
    sheet.append(header)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    sheet.freeze_panes = "A2"
    return sheet


def _fit(sheet: Worksheet) -> None:
    for index, column in enumerate(sheet.iter_cols(), start=1):
        width = max((len(str(cell.value)) for cell in column if cell.value is not None), default=4)
        sheet.column_dimensions[get_column_letter(index)].width = min(max(width + 2, 6), 50)


def _bytes(workbook: Workbook) -> bytes:
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _special(participation: Participation) -> str:
    parts = []
    if participation.guest_id:
        parts.append("extern")
    if participation.exception_by_id:
        parts.append("Ausnahme")
    if participation.off_target:
        parts.append("außerhalb der Zielgruppe")
    return ", ".join(parts)


def _guardians(participation: Participation) -> str:
    if participation.guest is not None:
        return participation.guest.guardian_name
    if participation.member is None:
        return ""
    return "; ".join(
        f"{user.display_name}{f' ({user.phone})' if user.phone else ''}"
        for user in members.guardians(participation.member)
    )


def participant_row(participation: Participation, on: date) -> list[Any]:
    person = participation.person
    club = participation.guest.club if participation.guest is not None else "Wedeler TSV"
    weight = participation.weight or person.weight
    return [
        person.last_name,
        person.first_name,
        participation.role.name,
        participation.get_status_display(),
        person.birth_date.year,
        age_in_year(person, on),
        person.get_gender_display(),
        person.grade_short,
        float(weight) if weight else None,
        club,
        participation.note,
        _special(participation),
        person.phone,
        _guardians(participation),
    ]


def _participations(occurrences: Any) -> Any:
    return (
        Participation.objects.filter(occurrence__in=occurrences, status__in=ACTIVE)
        .select_related("member", "guest", "role", "occurrence")
        .order_by("role__order", "member__last_name", "guest__last_name", "member__first_name", "guest__first_name")
    )


def occurrence_workbook(occurrence: Occurrence) -> bytes:
    """Teilnehmerliste eines Termins: erst die Übungsleiter, dann die Teilnehmer (mit Warteliste)."""
    workbook = Workbook()
    sheet = _sheet(workbook, "Teilnehmer", PARTICIPANT_COLUMNS, first=True)
    on = timezone.localdate(occurrence.starts_at)
    rows = sorted(_participations([occurrence]), key=lambda p: (not p.role.is_team, p.status != "registered"))
    for participation in rows:
        sheet.append(participant_row(participation, on))
    _fit(sheet)
    return _bytes(workbook)


def event_occurrences(event: Event, start: date | None = None, end: date | None = None) -> list[Occurrence]:
    occurrences = event.occurrences.order_by("starts_at")
    if start:
        occurrences = occurrences.filter(starts_at__date__gte=start)
    if end:
        occurrences = occurrences.filter(starts_at__date__lte=end)
    return list(occurrences)


def event_workbook(event: Event, start: date | None = None, end: date | None = None) -> bytes:
    """Blatt „Teilnahmen“: eine Zeile je Teilnahme. Blatt „Anwesenheit“: Personen × Termine mit x bzw. W."""
    occurrences = event_occurrences(event, start, end)
    workbook = Workbook()
    entries = _sheet(workbook, "Teilnahmen", ["Datum", "Beginn", "Termin", *PARTICIPANT_COLUMNS], first=True)
    participations = sorted(
        _participations(occurrences), key=lambda p: (p.occurrence.starts_at, not p.role.is_team, p.status)
    )
    for participation in participations:
        occurrence = participation.occurrence
        local = timezone.localtime(occurrence.starts_at)
        entries.append(
            [
                local.date(),
                local.strftime("%H:%M"),
                "abgesagt" if occurrence.is_cancelled else "",
                *participant_row(participation, local.date()),
            ]
        )
    for cell in entries["A"][1:]:
        cell.number_format = "DD.MM.YYYY"
    _fit(entries)

    columns = [timezone.localtime(o.starts_at).strftime("%d.%m.%Y %H:%M") for o in occurrences]
    matrix = _sheet(workbook, "Anwesenheit", ["Nachname", "Vorname", "Rolle", *columns, "Anzahl"])
    people: dict[tuple[str, int], dict[str, Any]] = {}
    index = {o.pk: i for i, o in enumerate(occurrences)}
    for participation in participations:
        key = ("m", participation.member_id) if participation.member_id else ("g", participation.guest_id)
        person = participation.person
        row = people.setdefault(
            key,
            {"name": [person.last_name, person.first_name], "roles": [], "cells": [""] * len(occurrences)},
        )
        if participation.role.name not in row["roles"]:
            row["roles"].append(participation.role.name)
        mark = "W" if participation.status == ParticipationStatus.WAITLIST else "x"
        row["cells"][index[participation.occurrence_id]] = mark
    for row in sorted(people.values(), key=lambda r: (r["name"][0].lower(), r["name"][1].lower())):
        matrix.append([*row["name"], ", ".join(row["roles"]), *row["cells"], row["cells"].count("x")])
    for i, occurrence in enumerate(occurrences, start=4):
        if occurrence.is_cancelled:
            matrix.cell(row=1, column=i).value = f"{columns[i - 4]} (abgesagt)"
    _fit(matrix)
    return _bytes(workbook)
