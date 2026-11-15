from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.core import mail
from django.utils import timezone

from portal.events import services
from portal.events.models import Event, RegistrationStatus, TargetGroup
from portal.events.services import RegistrationError
from portal.members.models import LinkKind, MemberLink

from .conftest import make_member, make_occurrence, make_user

pytestmark = pytest.mark.django_db


def test_register_and_unregister(child, parent):
    occurrence = make_occurrence()
    registration = services.register(occurrence, child, parent, note="komme später")
    assert registration.status == RegistrationStatus.REGISTERED
    assert registration.registered_by == parent
    services.unregister(registration, parent)
    assert registration.status == RegistrationStatus.CANCELLED
    assert services.register(occurrence, child, parent).status == RegistrationStatus.REGISTERED


def test_target_group_blocks_registration(child, parent):
    event = Event.objects.create(title="Erwachsene")
    event.target_groups.set([TargetGroup.objects.create(name="Erwachsene", min_age=18)])
    with pytest.raises(RegistrationError, match="passt nicht"):
        services.register(make_occurrence(event), child, parent)


def test_exception_ignores_target_group_window_and_capacity(child, trainer):
    event = Event.objects.create(title="Kader", capacity=0)
    event.target_groups.set([TargetGroup.objects.create(name="Erwachsene", min_age=18)])
    occurrence = make_occurrence(event, in_days=-0.01)
    registration = services.register(occurrence, child, trainer, exception=True)
    assert registration.status == RegistrationStatus.REGISTERED
    assert registration.exception_by == trainer


def test_fixed_registration_window(child, parent):
    now = timezone.now()
    event = Event.objects.create(
        title="Wettkampf", registration_opens_at=now + timedelta(days=1), registration_closes_at=now + timedelta(days=5)
    )
    occurrence = make_occurrence(event, in_days=10)
    assert services.window(occurrence) == "before"
    with pytest.raises(RegistrationError, match="öffnet am"):
        services.register(occurrence, child, parent)
    assert services.window(occurrence, now + timedelta(days=2)) == "open"
    assert services.window(occurrence, now + timedelta(days=6)) == "closed"


def test_relative_registration_window(child, parent):
    event = Event.objects.create(title="Training", opens_days_before=7, closes_hours_before=2)
    later = make_occurrence(event, in_days=8)
    soon = make_occurrence(event, in_days=0.05)  # in gut einer Stunde
    middle = make_occurrence(event, in_days=3)
    assert services.window(later) == "before"
    assert services.window(soon) == "closed"
    assert services.window(middle) == "open"
    assert services.register(middle, child, parent).status == RegistrationStatus.REGISTERED
    with pytest.raises(RegistrationError, match="geschlossen"):
        services.register(soon, child, parent)


def test_no_unregister_after_deadline_except_force(child, parent, trainer):
    event = Event.objects.create(title="Wettkampf")
    occurrence = make_occurrence(event)
    registration = services.register(occurrence, child, parent)
    event.registration_closes_at = timezone.now() - timedelta(minutes=1)
    event.save()
    registration.occurrence.refresh_from_db()
    with pytest.raises(RegistrationError, match="Anmeldeschluss"):
        services.unregister(registration, parent)
    services.unregister(registration, trainer, force=True)
    assert registration.status == RegistrationStatus.CANCELLED


def test_cancelled_occurrence_blocks(child, parent):
    occurrence = make_occurrence()
    services.cancel(occurrence)
    with pytest.raises(RegistrationError, match="abgesagt"):
        services.register(occurrence, child, parent)


def test_waitlist_and_promotion_with_mail(child, parent, django_capture_on_commit_callbacks):
    other_parent = make_user("zwei@example.org")
    other = make_member("Ben", age=10)
    MemberLink.objects.create(user=other_parent, member=other, kind=LinkKind.GUARDIAN)
    occurrence = make_occurrence(Event.objects.create(title="Lehrgang", kind="course", capacity=1))
    first = services.register(occurrence, child, parent)
    second = services.register(occurrence, other, other_parent)
    assert second.status == RegistrationStatus.WAITLIST
    with django_capture_on_commit_callbacks(execute=True):
        services.unregister(first, parent)
    second.refresh_from_db()
    assert second.status == RegistrationStatus.REGISTERED
    assert [m.to for m in mail.outbox] == [[other_parent.email]]
    assert "Nachgerückt" in mail.outbox[0].subject


def test_required_weight_is_stored_and_taken_into_profile(child, parent):
    occurrence = make_occurrence(Event.objects.create(title="Wettkampf", weight_required=True))
    registration = services.register(occurrence, child, parent, weight=Decimal("31.4"))
    child.refresh_from_db()
    assert registration.weight == Decimal("31.4")
    assert child.weight == Decimal("31.4")


def test_required_weight_falls_back_to_profile(child, trainer):
    child.weight = Decimal("30.0")
    child.save()
    occurrence = make_occurrence(Event.objects.create(title="Wettkampf", weight_required=True))
    assert services.register(occurrence, child, trainer, exception=True).weight == Decimal("30.0")


def test_agenda_sections_for_parent_with_two_children(parent, child):
    adult_group = TargetGroup.objects.create(name="Erwachsene", min_age=18)
    kids = Event.objects.create(title="Kindertraining")
    adults = Event.objects.create(title="Erwachsenentraining")
    adults.target_groups.set([adult_group])
    make_occurrence(kids)
    make_occurrence(adults)
    sibling = make_member("Ole", age=7)
    MemberLink.objects.create(user=parent, member=sibling, kind=LinkKind.GUARDIAN)
    sections = services.agenda(parent)
    assert [s.member.first_name for s in sections] == ["Mia", "Ole"]
    assert [i.occurrence.event.title for i in sections[0].items] == ["Kindertraining"]
    assert [i.occurrence.event.title for i in sections[0].others] == ["Erwachsenentraining"]
    assert sections[0].items[0].can_register
    assert not sections[0].others[0].can_register


def test_guardian_link_ends_at_18(parent):
    grown = make_member("Lea", age=18)
    MemberLink.objects.create(user=parent, member=grown, kind=LinkKind.GUARDIAN)
    make_occurrence()
    assert services.agenda(parent) == []
