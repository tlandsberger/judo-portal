"""Fest eingeteilte Übungsleiter legen Termine zu ihren Veranstaltungen an (ohne sich selbst einzutragen)."""

from __future__ import annotations

from datetime import time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from portal.core.models import AuditEntry
from portal.events import services
from portal.events.models import Event, Occurrence, Schedule, ScheduleTeam

from .conftest import PASSWORD, make_trainer, role

pytestmark = pytest.mark.django_db


def schedule_for(event: Event, **extra: object) -> Schedule:
    today = timezone.localdate()
    defaults = {"weekday": 1, "start_time": time(17), "end_time": time(18, 30), "valid_from": today}
    return Schedule.objects.create(event=event, **(defaults | extra))


def post_data(days: int = 5) -> dict[str, str]:
    starts = timezone.localtime() + timedelta(days=days)
    return {
        "starts_at": starts.strftime("%Y-%m-%dT18:00"),
        "ends_at": starts.strftime("%Y-%m-%dT19:30"),
    }


def login(client, user):
    assert client.login(email=user.email, password=PASSWORD)


def test_fixed_trainer_adds_occurrence(client, trainer):
    event = Event.objects.create(title="Kindertraining", capacity=12)
    ScheduleTeam.objects.create(schedule=schedule_for(event), member=services.own_member(trainer), role=role("Trainer"))
    login(client, trainer)
    assert (
        reverse("occurrence_create", args=[event.pk])
        in client.get(reverse("event_detail", args=[event.pk])).content.decode()
    )
    assert "team_counts" in client.get(reverse("occurrence_create", args=[event.pk])).context["form"].fields
    response = client.post(reverse("occurrence_create", args=[event.pk]), post_data() | {"team_counts": "ja"})
    occurrence = Occurrence.objects.get(event=event, schedule__isnull=True)
    assert occurrence.team_counts is True
    assert response.url == reverse("occurrence_detail", args=[occurrence.pk])
    assert not occurrence.participations.exists()  # nicht automatisch eingetragen
    assert AuditEntry.objects.filter(action="occurrence_create", actor=trainer).exists()


def test_others_may_not_add(client, trainer):
    event = Event.objects.create(title="Kindertraining")
    other = Event.objects.create(title="Lehrgang")
    member = services.own_member(trainer)
    # Abgelaufener Zeitplan zählt nicht, Einteilung an einem einzelnen Termin auch nicht
    yesterday = timezone.localdate() - timedelta(days=1)
    old = schedule_for(event, valid_from=yesterday - timedelta(days=30), valid_until=yesterday)
    ScheduleTeam.objects.create(schedule=old, member=member, role=role("Trainer"))
    login(client, trainer)
    for target in (event, other):
        assert client.get(reverse("occurrence_create", args=[target.pk])).status_code == 403
        assert client.post(reverse("occurrence_create", args=[target.pk]), post_data()).status_code == 403
        page = client.get(reverse("event_detail", args=[target.pk])).content.decode()
        assert reverse("occurrence_create", args=[target.pk]) not in page
    login(client, make_trainer("ben@example.org", "Ben"))
    assert client.get(reverse("occurrence_create", args=[event.pk])).status_code == 403


def test_head_still_adds(client, head):
    event = Event.objects.create(title="Lehrgang")
    login(client, head)
    assert client.post(reverse("occurrence_create", args=[event.pk]), post_data()).status_code == 302
    assert event.occurrences.count() == 1
