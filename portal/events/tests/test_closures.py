"""Ferien und Feiertage (ADR 0026): iCal-Import von schulferien.org, Auswahl am Zeitplan, Absagen und Wiederaufnahme."""

from __future__ import annotations

from datetime import date, time, timedelta
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from portal.events import closures, services
from portal.events.models import (
    Closure,
    ClosurePeriod,
    Event,
    Occurrence,
    Participation,
    ParticipationStatus,
    Schedule,
)

from .conftest import PASSWORD, role

pytestmark = pytest.mark.django_db


@pytest.fixture
def run_on_commit(django_capture_on_commit_callbacks):
    """Führt eine Funktion aus und danach die Callbacks nach dem Commit (Nachrichten)."""

    def runner(func, *args, **kwargs):
        with django_capture_on_commit_callbacks(execute=True):
            return func(*args, **kwargs)

    return runner


FIXTURES = Path(__file__).parent / "fixtures"
FERIEN = (FIXTURES / "ferien_schleswig-holstein_2026.ics").read_bytes()
FEIERTAGE = (FIXTURES / "feiertage_schleswig-holstein_2026.ics").read_bytes()


def test_parse_schulferien_org():
    ferien = closures.parse(FERIEN)
    assert {row.closure for row in ferien} == {
        "Winterferien",
        "Osterferien",
        "Pfingstferien",
        "Sommerferien",
        "Herbstferien",
        "Weihnachtsferien",
    }
    herbst = next(row for row in ferien if row.closure == "Herbstferien")
    # DTEND ist bei ganztägigen Einträgen exklusiv
    assert (herbst.name, herbst.first, herbst.last) == ("Herbstferien 2026", date(2026, 10, 12), date(2026, 10, 24))
    weihnachten = next(row for row in ferien if row.closure == "Weihnachtsferien")
    assert weihnachten.last == date(2027, 1, 6)
    feiertage = closures.parse(FEIERTAGE)
    assert {row.closure for row in feiertage} == {closures.HOLIDAYS}
    assert ("2. Weihnachtsfeiertag", date(2026, 12, 26), date(2026, 12, 26)) in {
        (row.name, row.first, row.last) for row in feiertage
    }
    with pytest.raises(closures.ImportError_):
        closures.parse(b"kein kalender")


def test_import_is_idempotent_even_with_new_uids():
    changed, _ = closures.import_rows(closures.parse(FERIEN) + closures.parse(FEIERTAGE))
    assert changed == 16
    assert Closure.objects.count() == 7
    # schulferien.org vergibt bei jedem Export neue UIDs: erkannt wird dann am Zeitraum
    again = closures.parse(FERIEN.replace(b"termin6afe", b"terminXXXX"))
    assert closures.preview(again).new_count == 0
    assert closures.import_rows(again)[0] == 0
    # geänderte Ferien (gleiche UID) werden angepasst
    moved = closures.parse(FERIEN.replace(b"DTEND;VALUE=DATE:20261025", b"DTEND;VALUE=DATE:20261026"))
    assert closures.preview(moved).groups["Herbstferien"]["changed"]
    closures.import_rows(moved)
    assert ClosurePeriod.objects.get(closure__name="Herbstferien").last == date(2026, 10, 25)


@pytest.fixture
def weekly(trainer):
    """Training jeden Tag der kommenden drei Wochen (so trifft jeder Zeitraum sicher einen Termin)."""
    event = Event.objects.create(title="Kindertraining")
    today = timezone.localdate()
    created = []
    for weekday in range(7):
        schedule = Schedule.objects.create(
            event=event,
            weekday=weekday,
            start_time=time(17),
            end_time=time(18, 30),
            valid_from=today + timedelta(days=1),
            valid_until=today + timedelta(days=21),
        )
        services.generate(schedule)
        created.append(schedule)
    return created


def period(closure: str, first_in: int, days: int = 1) -> ClosurePeriod:
    today = timezone.localdate()
    item, _ = Closure.objects.get_or_create(name=closure)
    first = today + timedelta(days=first_in)
    return ClosurePeriod.objects.create(closure=item, name=closure, first=first, last=first + timedelta(days=days - 1))


def in_period(schedules, p: ClosurePeriod):
    return Occurrence.objects.filter(
        schedule__in=schedules, starts_at__date__gte=p.first, starts_at__date__lte=p.last
    ).order_by("starts_at")


def test_selected_closures_cancel_and_restore(weekly, trainer, parent, child, run_on_commit):
    herbst = period("Herbstferien", 3, days=2)
    other = period("Sommerferien", 8)
    first = in_period(weekly, herbst).first()
    services.set_team(first, services.own_member(trainer), role("Trainer"))
    Participation.objects.create(
        occurrence=first, member=child, role=role("Teilnehmer"), status=ParticipationStatus.REGISTERED
    )
    batch = run_on_commit(lambda: [closures.set_schedule_closures(s, [herbst.closure], by=None) for s in weekly][-1])
    cancelled = list(in_period(weekly, herbst))
    assert len(cancelled) == 2 and all(o.is_cancelled and o.closure_period == herbst for o in cancelled)
    assert not any(o.is_cancelled for o in in_period(weekly, other))  # nicht ausgewählt
    # Eine gebündelte Nachricht je Benutzer und Eintrag, nur an Angemeldete und Übungsleiter
    from portal.notifications.models import SentNotification

    titles = list(SentNotification.objects.values_list("user__email", "title"))
    assert ("anna@example.org", "Herbstferien: 1 Termin fällt aus") in titles
    assert ("eltern@example.org", "Herbstferien: 1 Termin fällt aus") in titles
    assert batch is not None
    # Zeitraum löschen: die Termine finden wieder statt
    run_on_commit(closures.delete_periods, [herbst])
    assert not any(o.is_cancelled for o in in_period(weekly, herbst))
    assert ("anna@example.org", "Herbstferien: 1 Termin findet doch statt") in list(
        SentNotification.objects.values_list("user__email", "title")
    )


def test_manual_cancellations_and_exemptions_stay(weekly, head):
    feiertag = period(closures.HOLIDAYS, 4)
    occurrence = in_period(weekly, feiertag).get()
    for schedule in weekly:
        closures.set_schedule_closures(schedule, [feiertag.closure])
    occurrence.refresh_from_db()
    assert occurrence.is_cancelled
    # „Findet doch statt“: der nächste Abgleich sagt nicht wieder ab
    services.uncancel(occurrence, head)
    closures.sync(weekly)
    occurrence.refresh_from_db()
    assert not occurrence.is_cancelled and occurrence.closure_exempt
    # Von Hand abgesagt, dann Eintrag gelöscht: bleibt abgesagt
    manual = in_period(weekly, period("Brückentag", 6)).get()
    services.cancel(manual, head, notify=False)
    closures.delete_closure(Closure.objects.get(name="Brückentag"))
    manual.refresh_from_db()
    assert manual.is_cancelled and manual.closure_period is None


def test_new_occurrences_in_closures_are_cancelled(trainer):
    event = Event.objects.create(title="Training")
    today = timezone.localdate()
    schedule = Schedule.objects.create(
        event=event,
        weekday=(today + timedelta(days=2)).weekday(),
        start_time=time(17),
        end_time=time(18),
        valid_from=today,
        valid_until=today + timedelta(days=6),
    )
    schedule.closures.set([period("Herbstferien", 0, days=7).closure])
    services.generate(schedule)
    assert schedule.occurrences.get().is_cancelled


def login(client, user):
    assert client.login(email=user.email, password=PASSWORD)


def test_import_pages_only_for_head_with_preview(client, head, trainer):
    login(client, trainer)
    assert client.get(reverse("closure_list")).status_code == 403
    assert client.get(reverse("closure_import")).status_code == 403
    login(client, head)
    upload = SimpleUploadedFile("ferien.ics", FERIEN, content_type="text/calendar")
    page = client.post(reverse("closure_import"), {"file": upload}).content.decode()
    assert "Vorschau" in page and "Herbstferien 2026" in page and "6 Zeiträume übernehmen" in page
    assert not Closure.objects.exists()  # erst nach dem Übernehmen
    response = client.post(reverse("closure_import"), {"action": "confirm"})
    assert response.url == reverse("closure_list")
    assert ClosurePeriod.objects.count() == 6
    page = client.get(reverse("closure_list")).content.decode()
    assert "Sommerferien" in page
    bad = SimpleUploadedFile("ferien.txt", b"x", content_type="text/plain")
    assert "iCal-Datei (.ics)" in client.post(reverse("closure_import"), {"file": bad}).content.decode()


def test_manual_period_and_schedule_form(client, head, weekly):
    login(client, head)
    day = timezone.localdate() + timedelta(days=5)
    response = client.post(
        reverse("closure_list"), {"closure": "Brückentage", "name": "Brückentag", "first": day.isoformat()}
    )
    assert response.url == reverse("closure_list")
    closure = Closure.objects.get(name="Brückentage")
    assert closure.periods.get().last == day
    schedule = next(s for s in weekly if s.weekday == day.weekday())
    page = client.get(reverse("schedule_edit", args=[schedule.event_id, schedule.pk])).content.decode()
    assert "Brückentage" in page
