"""Abrechnungsrelevante Rollen nur mit Stundensatz: sonst weder angeboten noch auswählbar."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from portal.events import services as events
from portal.events.models import Event, Schedule
from portal.events.services import RegistrationError
from portal.events.tests.conftest import PASSWORD, event_type, make_occurrence

from .conftest import make_trainer, role, set_rate

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("rates_required")]


def training():
    return make_occurrence(Event.objects.create(title="Training", event_type=event_type("Training")))


def test_billable_role_needs_rate_on_the_day(trainer):
    occurrence = training()
    member = events.own_member(trainer)
    with pytest.raises(RegistrationError, match="kein Stundensatz"):
        events.set_team(occurrence, member, role("Trainer"))
    # Ein Satz, der erst nach dem Termin gilt, reicht nicht
    set_rate(trainer, "Trainer", valid_from=timezone.localdate(occurrence.starts_at) + timedelta(days=1))
    assert not events.can_take_role(member, role("Trainer"), occurrence.event, occurrence.starts_at.date())
    set_rate(trainer, "Trainer", valid_from=timezone.localdate() - timedelta(days=30))
    assert events.set_team(occurrence, member, role("Trainer")).role == role("Trainer")
    # Co-Trainer ist auch abrechnungsrelevant, Satz fehlt
    assert not events.can_take_role(member, role("Co-Trainer"), occurrence.event)


def test_roles_without_billing_need_no_rate(trainer):
    exam = make_occurrence(Event.objects.create(title="Prüfung", event_type=event_type("Prüfung")))
    assert events.set_team(exam, events.own_member(trainer), role("Prüfer")).role == role("Prüfer")


def test_hand_over_and_schedule_team_check_the_rate(trainer):
    other = make_trainer("ben@example.org", "Ben")
    set_rate(trainer, "Trainer")
    occurrence = training()
    participation = events.set_team(occurrence, events.own_member(trainer), role("Trainer"))
    with pytest.raises(RegistrationError, match="Für Ben ist als Trainer noch kein Stundensatz"):
        events.hand_over(participation, events.own_member(other), by=trainer)
    schedule = Schedule.objects.create(
        event=occurrence.event,
        weekday=0,
        start_time="17:00",
        end_time="18:30",
        valid_from=timezone.localdate(),
        valid_until=timezone.localdate() + timedelta(days=14),
    )
    with pytest.raises(RegistrationError, match="kein Stundensatz"):
        events.set_schedule_team(schedule, events.own_member(other), role("Co-Trainer"))


def test_occurrence_offers_only_roles_with_rate(client, trainer):
    occurrence = training()
    set_rate(trainer, "Co-Trainer")
    client.login(email=trainer.email, password=PASSWORD)
    response = client.get(reverse("occurrence_detail", args=[occurrence.pk]))
    assert [r.name for r in response.context["self_roles"]] == ["Co-Trainer"]
