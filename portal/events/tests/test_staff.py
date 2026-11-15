from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from portal.accounts.models import Role
from portal.events import services
from portal.events.models import Event, EventStaff, StaffFunction, Staffing

from .conftest import make_occurrence, make_user

pytestmark = pytest.mark.django_db


def test_only_trainers_can_be_staffed(parent):
    with pytest.raises(ValueError, match="kein Übungsleiter"):
        services.set_staffing(make_occurrence(), parent, StaffFunction.TRAINER)


def test_set_staffing_changes_function(trainer):
    occurrence = make_occurrence()
    services.set_staffing(occurrence, trainer, StaffFunction.CO_TRAINER)
    services.set_staffing(occurrence, trainer, StaffFunction.TRAINER)
    assert occurrence.staffings.get().function == StaffFunction.TRAINER


def test_default_staff_applies_to_future_occurrences(trainer):
    event = Event.objects.create(title="Training")
    past = make_occurrence(event, in_days=-2)
    future = make_occurrence(event, in_days=2)
    services.set_default_staff(event, trainer, StaffFunction.TRAINER)
    assert not past.staffings.exists()
    assert future.staffings.get().user == trainer
    services.remove_default_staff(EventStaff.objects.get())
    assert not future.staffings.exists()


def test_confirm_after_start_with_minutes(trainer):
    upcoming = services.set_staffing(make_occurrence(in_days=1), trainer, StaffFunction.TRAINER)
    with pytest.raises(ValueError, match="erst"):
        services.confirm(upcoming)
    done = services.set_staffing(make_occurrence(in_days=-1, hours=2), trainer, StaffFunction.CO_TRAINER)
    services.confirm(done)
    assert done.is_confirmed
    assert done.minutes == 120
    with pytest.raises(ValueError, match="bestätigte"):
        services.remove_staffing(done)


def test_lead_and_participant_rights(trainer, head, parent):
    other = make_user("tom@example.org", Role.TRAINER)
    occurrence = make_occurrence(in_days=-1)
    Staffing.objects.create(occurrence=occurrence, user=trainer, function=StaffFunction.TRAINER)
    assert services.can_lead(trainer, occurrence)
    assert services.can_see_participants(trainer, occurrence)
    assert not services.can_lead(other, occurrence)
    assert not services.can_see_participants(other, occurrence)
    assert not services.can_lead(parent, occurrence)
    assert services.can_see_participants(head, occurrence)
    later = timezone.now() + timedelta(days=services.PARTICIPANTS_DAYS_AFTER + 1)
    assert not services.can_see_participants(trainer, occurrence, later)


def test_participants_with_emergency_contact(child, parent, trainer):
    parent.phone = "0171 1234567"
    parent.save()
    child.phone = "04103 12345"
    child.save()
    occurrence = make_occurrence()
    services.register(occurrence, child, parent)
    [row] = services.participants(occurrence)
    assert row.member == child
    assert row.guardians == [parent]
    assert row.age == timezone.localdate().year - child.birth_date.year
