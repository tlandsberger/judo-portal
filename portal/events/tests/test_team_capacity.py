"""Übungsleiter wahlweise zur Höchstzahl gezählt (je Termin festlegbar)."""

from __future__ import annotations

from datetime import time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from portal.events import services
from portal.events.models import Event, ParticipationStatus, Schedule, ScheduleTeam
from portal.events.services import RegistrationError

from .conftest import PASSWORD, make_occurrence, make_trainer, role

pytestmark = pytest.mark.django_db


def login(client, user):
    assert client.login(email=user.email, password=PASSWORD)
    return client


def test_team_counts_only_when_set(trainer, parent, child):
    event = Event.objects.create(title="Training", capacity=2)
    occurrence = make_occurrence(event)
    services.set_team(occurrence, services.own_member(trainer), role("Trainer"))
    services.register(occurrence, child, parent)
    assert services.registered_count(occurrence) == 1
    event.team_counts = True
    event.save()
    assert services.registered_count(occurrence) == 2
    occurrence.team_counts = False  # Termin weicht ab
    assert services.registered_count(occurrence) == 1
    event.capacity = None  # ohne Höchstzahl zählt niemand mit
    occurrence.team_counts = True
    assert not occurrence.counts_team


def test_full_occurrence_only_head_overbooks_with_team(trainer, head, parent, child):
    event = Event.objects.create(title="Training", capacity=1, team_counts=True)
    occurrence = make_occurrence(event)
    services.register(occurrence, child, parent)
    anna = services.own_member(trainer)
    with pytest.raises(RegistrationError, match="nur die Abteilungsleitung"):
        services.set_team(occurrence, anna, role("Trainer"), trainer)
    services.set_team(occurrence, anna, role("Trainer"), head)
    assert services.registered_count(occurrence) == 2
    # Andere Rolle: belegt schon einen Platz, also kein Überbuchen
    services.set_team(occurrence, anna, role("Co-Trainer"), trainer)


def test_switch_to_team_keeps_place_when_counted(trainer, parent, child):
    event = Event.objects.create(title="Training", capacity=1, team_counts=True)
    occurrence = make_occurrence(event)
    anna = services.own_member(trainer)
    services.register(occurrence, anna, trainer)
    waiting = services.register(occurrence, child, parent)
    services.set_team(occurrence, anna, role("Co-Trainer"), trainer)
    waiting.refresh_from_db()
    assert waiting.status == ParticipationStatus.WAITLIST


def test_withdraw_and_setting_off_promote(trainer, head, parent, child):
    event = Event.objects.create(title="Training", capacity=1, team_counts=True)
    occurrence = make_occurrence(event)
    anna = services.set_team(occurrence, services.own_member(trainer), role("Co-Trainer"), head)
    waiting = services.register(occurrence, child, parent)
    assert waiting.status == ParticipationStatus.WAITLIST
    services.withdraw(anna, trainer)
    waiting.refresh_from_db()
    assert waiting.status == ParticipationStatus.REGISTERED

    other = make_occurrence(event)
    services.set_team(other, services.own_member(trainer), role("Co-Trainer"), head)
    waiting = services.register(other, child, parent)
    other.team_counts = False
    services.update_occurrence(other, ["team_counts"], head)
    waiting.refresh_from_db()
    assert waiting.status == ParticipationStatus.REGISTERED and other.is_modified


def test_event_setting_off_promotes_upcoming(client, trainer, head, parent, child):
    event = Event.objects.create(title="Training", capacity=1, team_counts=True)
    occurrence = make_occurrence(event)
    services.set_team(occurrence, services.own_member(trainer), role("Co-Trainer"), head)
    waiting = services.register(occurrence, child, parent)
    login(client, head)
    data = {"title": "Training", "event_type": event.event_type_id, "capacity": 1, "target_mode": "required"}
    client.post(reverse("event_edit", args=[event.pk]), {**data, "zg-TOTAL_FORMS": 0, "zg-INITIAL_FORMS": 0})
    event.refresh_from_db()
    assert not event.team_counts
    waiting.refresh_from_db()
    assert waiting.status == ParticipationStatus.REGISTERED


def test_places_count_team_when_set(client, trainer, parent, child):
    event = Event.objects.create(title="Training", capacity=10, team_counts=True)
    occurrence = make_occurrence(event)
    services.set_team(occurrence, services.own_member(trainer), role("Trainer"))
    services.register(occurrence, child, parent)
    login(client, trainer)
    page = client.get(reverse("occurrence_detail", args=[occurrence.pk])).content.decode()
    assert "Teilnehmer (1)" in page
    assert "2 von 10 angemeldet (mit Übungsleitern)" in page
    assert "Anna Trainer abmelden" not in page and "Mia" in page  # Übungsleiter stehen nicht in der Liste


def test_occurrence_setting_only_for_heads(client, trainer, head):
    event = Event.objects.create(title="Training", capacity=10)
    occurrence = make_occurrence(event)
    services.set_team(occurrence, services.own_member(trainer), role("Trainer"))
    login(client, trainer)
    page = client.get(reverse("occurrence_edit", args=[occurrence.pk])).content.decode()
    assert "zur Höchstzahl" not in page
    login(client, head)
    page = client.get(reverse("occurrence_edit", args=[occurrence.pk])).content.decode()
    assert "Wie bei der Veranstaltung (nein)" in page
    form = {
        "starts_at": occurrence.starts_at.strftime("%Y-%m-%dT%H:%M"),
        "ends_at": occurrence.ends_at.strftime("%Y-%m-%dT%H:%M"),
        "team_counts": "ja",
    }
    client.post(reverse("occurrence_edit", args=[occurrence.pk]), form)
    occurrence.refresh_from_db()
    assert occurrence.team_counts is True and occurrence.counts_team
    client.post(reverse("occurrence_edit", args=[occurrence.pk]), {**form, "team_counts": ""})
    occurrence.refresh_from_db()
    assert occurrence.team_counts is None


def test_schedule_team_removal_promotes(head, parent, child):
    event = Event.objects.create(title="Training", capacity=1, team_counts=True)
    today = timezone.localdate()
    schedule = Schedule.objects.create(
        event=event,
        weekday=(today + timedelta(days=2)).weekday(),
        start_time=time(17),
        end_time=time(18),
        valid_from=today,
        valid_until=today + timedelta(days=6),
    )
    services.generate(schedule)
    ben = make_trainer("ben@example.org", "Ben")
    services.set_schedule_team(schedule, services.own_member(ben), role("Trainer"))
    occurrence = schedule.occurrences.get()
    waiting = services.register(occurrence, child, parent)
    assert waiting.status == ParticipationStatus.WAITLIST
    services.remove_schedule_team(ScheduleTeam.objects.get(schedule=schedule))
    waiting.refresh_from_db()
    assert waiting.status == ParticipationStatus.REGISTERED
