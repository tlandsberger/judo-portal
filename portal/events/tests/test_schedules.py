from __future__ import annotations

from datetime import time, timedelta

import pytest
from django.core import mail
from django.utils import timezone

from portal.events import services
from portal.events.models import Event, Participation, Schedule

from .conftest import make_occurrence, role

pytestmark = pytest.mark.django_db


def schedule(event: Event, weekday: int, weeks: int = 4, start: time = time(17)) -> Schedule:
    today = timezone.localdate()
    return Schedule.objects.create(
        event=event,
        weekday=weekday,
        start_time=start,
        end_time=time(18, 30),
        valid_from=today,
        valid_until=today + timedelta(weeks=weeks) - timedelta(days=1),
    )


def test_generate_from_several_schedules_with_default_staff(trainer):
    event = Event.objects.create(title="Training U12")
    tuesday = schedule(event, 1)
    tuesday.team.create(member=services.own_member(trainer), role=role("Trainer"))
    assert services.generate(tuesday) == 4
    assert services.generate(schedule(event, 3)) == 4
    occurrences = list(event.occurrences.all())
    assert len(occurrences) == 8
    assert {timezone.localtime(o.starts_at).weekday() for o in occurrences} == {1, 3}
    team = [o for o in occurrences if o.participations.filter(member__links__user=trainer).exists()]
    assert {timezone.localtime(o.starts_at).weekday() for o in team} == {1} and len(team) == 4
    assert services.generate(event.schedules.first()) == 0  # keine Doppelten


def test_open_schedule_limited_to_horizon():
    event = Event.objects.create(title="Training")
    plan = Schedule.objects.create(
        event=event, weekday=0, start_time=time(17), end_time=time(18), valid_from=timezone.localdate()
    )
    created = services.generate(plan)
    assert 51 <= created <= 53
    assert plan.generated_until == timezone.localdate() + timedelta(days=services.HORIZON_DAYS)


def test_regenerate_keeps_occurrences_with_registrations(child, parent):
    event = Event.objects.create(title="Training")
    plan = schedule(event, (timezone.localdate() + timedelta(days=2)).weekday())
    services.generate(plan)
    first = event.occurrences.first()
    services.register(first, child, parent)
    plan.start_time, plan.end_time = time(18), time(19, 30)
    plan.save()
    kept = services.regenerate(plan)
    assert kept == [first]
    assert event.occurrences.count() == 4
    assert Participation.objects.get().occurrence == first
    later = event.occurrences.exclude(pk=first.pk)
    assert all(timezone.localtime(o.starts_at).hour == 18 for o in later)


def test_delete_schedule_keeps_registered_as_single(child, parent):
    event = Event.objects.create(title="Training")
    plan = schedule(event, (timezone.localdate() + timedelta(days=2)).weekday())
    services.generate(plan)
    services.register(event.occurrences.first(), child, parent)
    assert services.delete_schedule(plan) == 1
    assert event.occurrences.get().schedule is None


def test_modified_occurrence_survives_regeneration():
    event = Event.objects.create(title="Training")
    plan = schedule(event, (timezone.localdate() + timedelta(days=2)).weekday())
    services.generate(plan)
    first = event.occurrences.first()
    first.location = "Turnhalle Nord"
    services.update_occurrence(first, ["location"])
    services.regenerate(plan)
    first.refresh_from_db()
    assert first.location == "Turnhalle Nord"


def test_cancel_range_mails_participants_and_staff(child, parent, trainer, django_capture_on_commit_callbacks):
    event = Event.objects.create(title="Training")
    plan = schedule(event, (timezone.localdate() + timedelta(days=2)).weekday())
    plan.team.create(member=services.own_member(trainer), role=role("Trainer"))
    services.generate(plan)
    first = event.occurrences.first()
    services.register(first, child, parent)
    start = timezone.localdate(first.starts_at)
    with django_capture_on_commit_callbacks(execute=True):
        count = services.cancel_range(event, start, start + timedelta(days=7))
    assert count == 2
    assert event.occurrences.filter(cancelled_at__isnull=False).count() == 2
    recipients = sorted(m.to[0] for m in mail.outbox)
    assert recipients.count(parent.email) == 1
    assert recipients.count(trainer.email) == 2
    assert "Abgesagt" in mail.outbox[0].subject


def test_ensure_generated_fills_new_schedule():
    event = Event.objects.create(title="Training")
    schedule(event, 2)
    services.ensure_generated()
    assert event.occurrences.count() == 4


def test_occurrence_minutes():
    assert make_occurrence(hours=1.5).minutes == 90


def test_registration_window_from_schedule_rule():
    event = Event.objects.create(title="Training")
    plan = schedule(event, (timezone.localdate() + timedelta(days=3)).weekday())
    plan.opens_hours_before, plan.closes_hours_before = 48, 2
    plan.save()
    services.generate(plan)
    first = event.occurrences.first()
    assert first.registration_opens == first.starts_at - timedelta(hours=48)
    assert first.registration_closes == first.starts_at - timedelta(hours=2)
    plan.closes_hours_before = 1
    plan.save()
    services.regenerate(plan)
    assert all(o.registration_closes == o.starts_at - timedelta(hours=1) for o in event.occurrences.all())


# Rhythmus: alle x Wochen oder jeden n-ten im Monat


def _plan(**rhythm: object) -> Schedule:
    from datetime import date

    return Schedule(
        event=Event(title="Training"),
        weekday=1,
        start_time=time(17),
        end_time=time(18),
        valid_from=date(2026, 12, 3),  # ein Donnerstag; erster Dienstag danach: 8.12.
        **rhythm,
    )


def test_every_two_weeks_counted_from_valid_from_across_new_year():
    from datetime import date

    days = list(services.schedule_dates(_plan(interval=2), date(2026, 12, 1), date(2027, 2, 1)))
    assert days == [date(2026, 12, 8), date(2026, 12, 22), date(2027, 1, 5), date(2027, 1, 19)]
    # Später begonnen: derselbe Takt, nicht ab dem Starttag neu gezählt.
    assert next(services.schedule_dates(_plan(interval=2), date(2026, 12, 23), date(2027, 2, 1))) == date(2027, 1, 5)
    assert services.on_schedule(_plan(interval=2), date(2027, 1, 19))
    assert not services.on_schedule(_plan(interval=2), date(2027, 1, 12))


def test_nth_and_last_weekday_of_month():
    from datetime import date

    first = list(services.schedule_dates(_plan(repeat="month", week_of_month=1), date(2026, 12, 1), date(2027, 3, 1)))
    assert first == [date(2026, 12, 1), date(2027, 1, 5), date(2027, 2, 2)]
    last = list(services.schedule_dates(_plan(repeat="month", week_of_month=-1), date(2026, 12, 1), date(2027, 3, 1)))
    assert last == [date(2026, 12, 29), date(2027, 1, 26), date(2027, 2, 23)]
    assert services.nth_weekday(2027, 2, 1, 5) is None  # einen 5. Dienstag gibt es im Februar 2027 nicht


def test_rhythm_labels():
    assert str(_plan()) == "Dienstag 17:00–18:00"
    assert str(_plan(interval=2)) == "Dienstag 17:00–18:00, alle 2 Wochen"
    assert str(_plan(repeat="month", week_of_month=1)) == "1. Dienstag im Monat 17:00–18:00"
    assert str(_plan(repeat="month", week_of_month=-1)) == "Letzter Dienstag im Monat 17:00–18:00"
    assert _plan(repeat="month", week_of_month=3).rhythm_label == "jeden 3. Dienstag im Monat"


def test_generate_every_two_weeks_and_regenerate_after_change():
    event = Event.objects.create(title="Training")
    plan = schedule(event, (timezone.localdate() + timedelta(days=1)).weekday(), weeks=8)
    plan.interval = 2
    plan.save()
    assert services.generate(plan) == 4
    plan.repeat, plan.week_of_month, plan.interval = "month", 1, 1
    plan.save()
    services.regenerate(plan)
    starts = [timezone.localtime(o.starts_at).date() for o in event.occurrences.all()]
    assert starts and all(day.day <= 7 for day in starts)


def test_schedule_form_requires_matching_rhythm_field(client, head):
    from django.urls import reverse

    event = Event.objects.create(title="Training")
    client.force_login(head)
    data = {
        "weekday": 5,
        "repeat": "month",
        "interval": "",
        "week_of_month": "",
        "start_time": "10:00",
        "end_time": "12:00",
        "valid_from": timezone.localdate().isoformat(),
    }
    url = reverse("schedule_create", args=[event.pk])
    assert "der wievielte im Monat" in client.post(url, data).content.decode()
    client.post(url, data | {"week_of_month": "1", "interval": "3"})
    saved = Schedule.objects.get(event=event)
    assert (saved.repeat, saved.week_of_month, saved.interval) == ("month", 1, 1)
