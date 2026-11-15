from __future__ import annotations

from datetime import time, timedelta

import pytest
from django.core import mail
from django.utils import timezone

from portal.events import services
from portal.events.models import Event, EventStaff, Registration, Schedule, StaffFunction

from .conftest import make_occurrence

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
    EventStaff.objects.create(event=event, user=trainer, function=StaffFunction.TRAINER)
    assert services.generate(schedule(event, 1)) == 4
    assert services.generate(schedule(event, 3)) == 4
    occurrences = list(event.occurrences.all())
    assert len(occurrences) == 8
    assert {timezone.localtime(o.starts_at).weekday() for o in occurrences} == {1, 3}
    assert all(o.staffings.get().user == trainer for o in occurrences)
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
    assert Registration.objects.get().occurrence == first
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
    EventStaff.objects.create(event=event, user=trainer, function=StaffFunction.TRAINER)
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
