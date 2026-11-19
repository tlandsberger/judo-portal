"""Ferien und Feiertage (ADR 0026): benannte Gruppen von Zeiträumen, Import aus iCal (z. B. schulferien.org).

Zeitpläne wählen aus, in welchen Ferien und an welchen Feiertagen sie ausfallen. Ihre kommenden Termine in diesen
Zeiträumen fallen aus und tragen den Zeitraum (``Occurrence.closure_period``), damit Ändern und Löschen sie wieder
stattfinden lässt. Wer schon angemeldet oder eingeteilt ist, bekommt je Gruppe (z. B. „Herbstferien“) eine
gebündelte Nachricht.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from django.db import transaction
from django.urls import reverse
from django.utils import formats, timezone

from portal.accounts.models import User
from portal.core import audit
from portal.notifications import services as notifications

from .models import Closure, ClosurePeriod, Occurrence, Schedule

log = logging.getLogger(__name__)

HOLIDAYS = "Gesetzliche Feiertage"
STATES = (
    "Baden-Württemberg",
    "Bayern",
    "Berlin",
    "Brandenburg",
    "Bremen",
    "Hamburg",
    "Hessen",
    "Mecklenburg-Vorpommern",
    "Niedersachsen",
    "Nordrhein-Westfalen",
    "Rheinland-Pfalz",
    "Saarland",
    "Sachsen-Anhalt",
    "Sachsen",
    "Schleswig-Holstein",
    "Thüringen",
)
MAX_DAYS = 120  # längere Einträge sind sicher kein Ferien- oder Feiertag (z. B. ein Kalender-Abo-Hinweis)


class ImportError_(Exception):
    pass


# Import


@dataclass(frozen=True)
class Row:
    """Ein Eintrag aus der iCal-Datei, schon einer Gruppe (z. B. „Herbstferien“) zugeordnet."""

    closure: str
    name: str
    first: date
    last: date
    uid: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "closure": self.closure,
            "name": self.name,
            "first": self.first.isoformat(),
            "last": self.last.isoformat(),
            "uid": self.uid,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> Row:
        return cls(
            data["closure"],
            data["name"],
            date.fromisoformat(data["first"]),
            date.fromisoformat(data["last"]),
            data["uid"],
        )


def _tidy(text: str) -> str:
    text = re.sub(r"\(\s*\)", "", text)
    return re.sub(r"\s+", " ", text).strip(" -–,:/()")


def _without_state(text: str) -> str:
    """„Herbstferien 2026 Schleswig-Holstein“ → „Herbstferien 2026“."""
    for state in STATES:
        text = re.sub(rf"(?<![\w-]){re.escape(state)}(?![\w-])", "", text, flags=re.IGNORECASE)
    return _tidy(text)


def _clean(text: str) -> str:
    """„Herbstferien 2026 Schleswig-Holstein“ → „Herbstferien“; Jahre und Bundesländer fallen weg."""
    return _tidy(re.sub(r"\b\d{4}(\s*/\s*\d{2,4})?\b", "", _without_state(text)))


def _day(value: Any) -> date:
    if isinstance(value, datetime):
        return timezone.localdate(value) if timezone.is_aware(value) else value.date()
    if isinstance(value, date):
        return value
    raise ImportError_("Ein Eintrag hat kein gültiges Datum.")


def parse(data: bytes) -> list[Row]:
    """Liest eine iCal-Datei: Einträge mit „ferien“ im Namen werden je Ferienart eine Gruppe, alle übrigen
    landen in „Gesetzliche Feiertage“. Ganztägige Einträge enden laut iCal am Folgetag (exklusiv)."""
    from icalendar import Calendar

    try:
        calendar = Calendar.from_ical(data)
    except ValueError as error:
        raise ImportError_("Die Datei ist keine gültige iCal-Datei (.ics).") from error
    rows: list[Row] = []
    for event in calendar.walk("VEVENT"):
        summary = str(event.get("SUMMARY", "")).strip()
        start = event.get("DTSTART")
        if not summary or start is None:
            continue
        first = _day(start.dt)
        end = event.get("DTEND")
        if end is not None:
            last = _day(end.dt)
            if not isinstance(end.dt, datetime):
                last -= timedelta(days=1)  # ganztägig: DTEND ist der Tag danach
        else:
            last = first
        last = max(last, first)
        if (last - first).days > MAX_DAYS:
            continue
        name = _without_state(summary) or summary
        closure = (_clean(summary) or summary) if "ferien" in summary.lower() else HOLIDAYS
        rows.append(Row(closure[:80], name[:120], first, last, str(event.get("UID", ""))[:255]))
    if not rows:
        raise ImportError_("In der Datei stehen keine Ferien oder Feiertage.")
    return sorted(rows, key=lambda row: (row.closure, row.first))


@dataclass
class Preview:
    """Was ein Import ändern würde, je Gruppe: neue, geänderte und schon vorhandene Zeiträume."""

    groups: dict[str, dict[str, list[Row]]] = field(default_factory=dict)

    @property
    def new_count(self) -> int:
        return sum(len(g["new"]) + len(g["changed"]) for g in self.groups.values())


def _existing(row: Row) -> ClosurePeriod | None:
    periods = ClosurePeriod.objects.filter(closure__name=row.closure)
    if row.uid:
        found = periods.filter(uid=row.uid).first()
        if found:
            return found
    return periods.filter(first=row.first, last=row.last).first()


def preview(rows: Iterable[Row]) -> Preview:
    result = Preview()
    for row in rows:
        group = result.groups.setdefault(row.closure, {"new": [], "changed": [], "known": []})
        existing = _existing(row)
        if existing is None:
            group["new"].append(row)
        elif (existing.first, existing.last, existing.name) != (row.first, row.last, row.name):
            group["changed"].append(row)
        else:
            group["known"].append(row)
    return result


@transaction.atomic
def import_rows(rows: Iterable[Row], by: User | None = None) -> tuple[int, Batch]:
    """Legt Gruppen (z. B. „Herbstferien“) und Zeiträume an bzw. passt sie an und sagt betroffene Termine ab."""
    changed = 0
    closures: set[int] = set()
    for row in rows:
        closure, _ = Closure.objects.get_or_create(name=row.closure)
        existing = _existing(row)
        if existing is None:
            ClosurePeriod.objects.create(closure=closure, name=row.name, first=row.first, last=row.last, uid=row.uid)
        elif (existing.first, existing.last, existing.name) != (row.first, row.last, row.name):
            existing.first, existing.last, existing.name = row.first, row.last, row.name
            existing.save(update_fields=["first", "last", "name"])
        else:
            continue
        changed += 1
        closures.add(closure.pk)
    if changed:
        audit.log(by, audit.Area.EVENTS, "closure_import", f"Ferien und Feiertage importiert ({changed} Zeiträume)")
    batch = sync(Schedule.objects.filter(closures__in=closures).distinct(), by=by)
    return changed, batch


# Von Hand


@transaction.atomic
def add_period(closure_name: str, name: str, first: date, last: date, by: User | None = None) -> Batch:
    closure, _ = Closure.objects.get_or_create(name=closure_name.strip())
    ClosurePeriod.objects.get_or_create(closure=closure, first=first, last=last, defaults={"name": name.strip()})
    audit.log(by, audit.Area.EVENTS, "closure_period", f"{closure}: {name} {first:%d.%m.%Y}–{last:%d.%m.%Y}")
    return sync(Schedule.objects.filter(closures=closure), by=by)


@transaction.atomic
def delete_periods(periods: Iterable[ClosurePeriod], by: User | None = None) -> Batch:
    """Zeiträume löschen; ihre abgesagten Termine finden wieder statt, außer ein anderer Zeitraum greift."""
    periods = list(periods)
    schedules = set(Schedule.objects.filter(closures__periods__in=periods).values_list("pk", flat=True))
    batch = Batch(by)
    for occurrence in Occurrence.objects.filter(closure_period__in=periods).select_related("event", "closure_period"):
        batch.restore(occurrence)
    for period in periods:
        audit.log(by, audit.Area.EVENTS, "closure_period_delete", f"Zeitraum gelöscht: {period}")
        period.delete()
    sync(Schedule.objects.filter(pk__in=schedules), by=by, batch=batch)
    return batch


@transaction.atomic
def delete_closure(closure: Closure, by: User | None = None) -> Batch:
    batch = delete_periods(closure.periods.all(), by)
    audit.log(by, audit.Area.EVENTS, "closure_delete", f"„{closure}“ aus Ferien und Feiertage gelöscht")
    closure.delete()
    return batch


@transaction.atomic
def set_schedule_closures(schedule: Schedule, closures: Iterable[Closure], by: User | None = None) -> Batch:
    schedule.closures.set(list(closures))
    return sync([schedule], by=by)


# Abgleich


class Batch:
    """Sammelt Absagen und Wiederaufnahmen eines Abgleichs; Nachrichten gehen gebündelt je Benutzer und Gruppe
    nach dem Commit raus."""

    def __init__(self, by: User | None = None) -> None:
        self.by = by
        self.cancelled: list[Occurrence] = []
        self.restored: list[Occurrence] = []
        self._sent = False

    def cancel(self, occurrence: Occurrence, period: ClosurePeriod) -> None:
        occurrence.cancelled_at = timezone.now()
        occurrence.closure_period = period
        occurrence.save(update_fields=["cancelled_at", "closure_period"])
        audit.log(self.by, audit.Area.EVENTS, "cancel", f"{_when(occurrence)} fällt aus: {period.closure}")
        self.cancelled.append(occurrence)

    def restore(self, occurrence: Occurrence) -> None:
        was_cancelled = occurrence.is_cancelled
        closure = occurrence.closure_period.closure if occurrence.closure_period else None
        occurrence.cancelled_at = None
        occurrence.closure_period = None
        occurrence.closure_exempt = False
        occurrence.save(update_fields=["cancelled_at", "closure_period", "closure_exempt"])
        if was_cancelled:
            occurrence._closure_name = str(closure or "")  # type: ignore[attr-defined]
            audit.log(self.by, audit.Area.EVENTS, "uncancel", f"{_when(occurrence)} findet wieder statt")
            self.restored.append(occurrence)

    def send(self) -> None:
        if self._sent:
            return
        self._sent = True
        cancelled = [(o, str(o.closure_period.closure)) for o in self.cancelled if o.closure_period]
        restored = [(o, getattr(o, "_closure_name", "")) for o in self.restored]
        if cancelled or restored:
            transaction.on_commit(lambda: _notify(cancelled, restored, self.by))


def _when(occurrence: Occurrence) -> str:
    return formats.date_format(timezone.localtime(occurrence.starts_at), "D d.m.Y H:i")


def sync(
    schedules: Iterable[Schedule], *, by: User | None = None, batch: Batch | None = None, notify: bool = True
) -> Batch:
    """Kommende Termine der Zeitpläne an ihre Ferien und Feiertage angleichen."""
    batch = batch or Batch(by)
    now = timezone.now()
    for schedule in schedules:
        periods = list(ClosurePeriod.objects.filter(closure__schedules=schedule).select_related("closure"))
        for occurrence in schedule.occurrences.filter(starts_at__gte=now).select_related("event", "closure_period"):
            day = timezone.localdate(occurrence.starts_at)
            period = next((p for p in periods if p.covers(day)), None)
            if period is not None:
                if occurrence.closure_exempt:
                    continue
                if not occurrence.is_cancelled:
                    batch.cancel(occurrence, period)
                elif occurrence.closure_period_id and occurrence.closure_period_id != period.pk:
                    occurrence.closure_period = period
                    occurrence.save(update_fields=["closure_period"])
            elif occurrence.closure_period_id:
                batch.restore(occurrence)
    if notify:
        batch.send()
    return batch


def exempt(occurrence: Occurrence) -> None:
    """„Findet doch statt“ an einem Termin in den Ferien oder an einem Feiertag: der nächste Abgleich sagt ihn nicht
    wieder ab."""
    if occurrence.closure_period_id:
        occurrence.closure_exempt = True
        occurrence.save(update_fields=["closure_exempt"])


# Nachrichten


def _notify(cancelled: list[tuple[Occurrence, str]], restored: list[tuple[Occurrence, str]], by: User | None) -> None:
    from . import guests, services

    stamp = timezone.now().strftime("%Y%m%d%H%M%S")
    for kind, rows in (("cancelled", cancelled), ("restored", restored)):
        per_user: dict[tuple[int, str], list[Occurrence]] = defaultdict(list)
        users: dict[int, User] = {}
        for occurrence, closure in rows:
            for user in services.participant_users(occurrence):
                if user != by:
                    users[user.pk] = user
                    per_user[(user.pk, closure)].append(occurrence)
            title = f"{'Abgesagt' if kind == 'cancelled' else 'Findet statt'}: {occurrence.event.title}"
            text = "fällt aus" if kind == "cancelled" else "findet doch statt"
            guests.notify(occurrence, title, f"{occurrence.event.title} am {_when(occurrence)} {text} ({closure}).")
        for (user_pk, closure), occurrences in per_user.items():
            lines = ", ".join(f"{o.event.title} {_when(o)}" for o in occurrences[:6])
            more = f" und {len(occurrences) - 6} weitere" if len(occurrences) > 6 else ""
            count = len(occurrences)
            if kind == "cancelled":
                title = f"{closure}: {count} Termin{'e fallen' if count > 1 else ' fällt'} aus"
            else:
                title = f"{closure}: {count} Termin{'e finden' if count > 1 else ' findet'} doch statt"
            notifications.notify(
                users[user_pk],
                key=f"closure-{kind}:{closure}:{user_pk}:{stamp}",
                kind="cancelled",
                title=title,
                body=f"{lines}{more}.",
                url=reverse("occurrence_detail", args=[occurrences[0].pk]) if count == 1 else reverse("agenda"),
            )
