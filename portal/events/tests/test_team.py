"""Teilnahme mit Rollen: eine Rolle je Person und Termin, Team, Stunden, Standard-Team am Zeitplan (ADR 0012)."""

from __future__ import annotations

from datetime import time, timedelta

import pytest
from django.utils import timezone

from portal.events import services
from portal.events.models import Event, ParticipationStatus, Schedule, ScheduleTeam
from portal.events.services import RegistrationError

from .conftest import event_type, make_occurrence, make_trainer, make_user, role

pytestmark = pytest.mark.django_db


def test_seeded_roles():
    assert services.default_role().name == "Teilnehmer"
    assert [r.name for r in services.team_roles()] == ["Trainer", "Co-Trainer", "Prüfer", "Betreuer"]
    training = Event.objects.create(title="Training")
    assert [r.name for r in services.team_roles(training)] == ["Trainer", "Co-Trainer"]
    exam = Event.objects.create(title="Gürtelprüfung", event_type=event_type("Prüfung"))
    assert [r.name for r in services.team_roles(exam)] == ["Prüfer"]


def test_team_role_needs_user_role_and_own_member(trainer, parent, child):
    occurrence = make_occurrence()
    anna = services.own_member(trainer)
    services.set_team(occurrence, anna, role("Trainer"))
    with pytest.raises(RegistrationError, match="nicht Trainer"):
        services.set_team(occurrence, child, role("Trainer"))
    with pytest.raises(RegistrationError, match="nicht Prüfer"):
        services.set_team(occurrence, anna, role("Prüfer"))  # nicht bei Trainings
    assert services.team_candidates(occurrence.event) == [anna]


def test_one_role_per_person_and_switch_frees_place(trainer, parent, child):
    event = Event.objects.create(title="Training", capacity=1)
    occurrence = make_occurrence(event)
    anna = services.own_member(trainer)
    services.register(occurrence, anna, trainer)
    waiting = services.register(occurrence, child, parent)
    assert waiting.status == ParticipationStatus.WAITLIST
    services.set_team(occurrence, anna, role("Co-Trainer"))
    waiting.refresh_from_db()
    assert waiting.status == ParticipationStatus.REGISTERED
    assert occurrence.participations.count() == 2
    assert services.registered_count(occurrence) == 1  # Team zählt nicht
    with pytest.raises(RegistrationError, match="als Co-Trainer eingetragen"):
        services.register(occurrence, anna, trainer)
    services.set_team(occurrence, anna, role("Trainer"))
    assert [p.role.name for p in services.team(occurrence)] == ["Trainer"]


def test_confirm_only_billable_after_start(trainer):
    anna = services.own_member(trainer)
    upcoming = services.set_team(make_occurrence(in_days=1), anna, role("Trainer"))
    with pytest.raises(RegistrationError, match="erst"):
        services.confirm(upcoming)
    done = services.set_team(make_occurrence(in_days=-1, hours=2), anna, role("Co-Trainer"))
    services.confirm(done)
    assert done.is_confirmed and done.minutes == 120
    with pytest.raises(RegistrationError, match="Bestätigte"):
        services.remove_team(done)
    competition = Event.objects.create(title="Turnier", event_type=event_type("Wettkampf"))
    carer = services.set_team(make_occurrence(competition, in_days=-1), anna, role("Betreuer"))
    with pytest.raises(RegistrationError, match="keine Stunden"):
        services.confirm(carer)


def test_lead_and_participant_rights(trainer, head, parent):
    other = make_trainer("tom@example.org", "Tom")
    occurrence = make_occurrence(in_days=-1)
    services.set_team(occurrence, services.own_member(trainer), role("Trainer"))
    assert services.can_lead(trainer, occurrence)
    assert services.can_see_participants(trainer, occurrence)
    assert not services.can_lead(other, occurrence)
    assert not services.can_see_participants(other, occurrence)
    assert not services.can_lead(parent, occurrence)
    assert services.can_see_participants(head, occurrence)
    later = timezone.now() + timedelta(days=services.PARTICIPANTS_DAYS_AFTER + 1)
    assert not services.can_see_participants(trainer, occurrence, later)


def test_can_join_team(trainer, parent):
    assert services.can_join_team(trainer)
    assert not services.can_join_team(parent)
    lonely = make_user("ohne@example.org", "trainer")
    assert not services.can_join_team(lonely)  # kein eigenes Mitgliedsprofil
    assert services.users_without_member(["trainer"]) == [lonely]


def test_schedule_team_follows_changes(trainer):
    event = Event.objects.create(title="Training")
    today = timezone.localdate()
    plan = Schedule.objects.create(
        event=event,
        weekday=(today + timedelta(days=2)).weekday(),
        start_time=time(17),
        end_time=time(18),
        valid_from=today,
        valid_until=today + timedelta(days=20),
    )
    services.generate(plan)
    anna = services.own_member(trainer)
    services.set_schedule_team(plan, anna, role("Trainer"))
    assert all(o.participations.get().role.name == "Trainer" for o in event.occurrences.all())
    services.set_schedule_team(plan, anna, role("Co-Trainer"))
    assert {p.role.name for o in event.occurrences.all() for p in o.participations.all()} == {"Co-Trainer"}
    services.remove_schedule_team(ScheduleTeam.objects.get())
    assert not any(o.participations.exists() for o in event.occurrences.all())


def test_participants_without_team_with_emergency_contact(child, parent, trainer):
    parent.phone = "0171 1234567"
    parent.save()
    occurrence = make_occurrence()
    services.register(occurrence, child, parent)
    services.set_team(occurrence, services.own_member(trainer), role("Trainer"))
    [row] = services.participants(occurrence)
    assert row.member == child
    assert row.guardians == [parent]
    assert row.age == timezone.localdate().year - child.birth_date.year


def test_unconfirm_until_submitted(trainer):
    occurrence = make_occurrence(in_days=-1)
    participation = services.set_team(occurrence, services.own_member(trainer), role("Trainer"))
    services.confirm(participation, 60)
    services.unconfirm(participation, by=trainer)
    participation.refresh_from_db()
    assert participation.confirmed_at is None and participation.minutes is None
    services.confirm(participation)
    assert participation.is_confirmed


def test_open_confirmations_for_start_page(trainer, client):
    from django.urls import reverse

    member = services.own_member(trainer)
    past = services.set_team(make_occurrence(in_days=-1), member, role("Trainer"))
    services.set_team(make_occurrence(in_days=2), member, role("Trainer"))  # Zukunft zählt nicht
    exam = Event.objects.create(title="Prüfung", event_type=event_type("Prüfung"))
    services.set_team(make_occurrence(exam, in_days=-1), member, role("Prüfer"))  # nicht abrechnungsrelevant
    assert services.open_confirmations(trainer) == [past]
    client.force_login(trainer)
    page = client.get(reverse("home")).content.decode()
    assert 'id="h-stunden"' in page and reverse("hours_confirm", args=[past.occurrence_id]) in page
    # Bestätigen auf der Startseite führt dorthin zurück.
    response = client.post(reverse("hours_confirm", args=[past.occurrence_id]), {"minutes": 60, "next": "/"})
    assert response.status_code == 302 and response.url == "/"
    assert services.open_confirmations(trainer) == []
    assert 'id="h-stunden"' not in client.get(reverse("home")).content.decode()


def test_open_confirmations_skip_locked(trainer):
    member = services.own_member(trainer)
    past = services.set_team(make_occurrence(in_days=-1), member, role("Trainer"))

    def lock(participation):
        return "eingereicht" if participation.pk == past.pk else None

    services.register_lock(lock)
    try:
        assert services.open_confirmations(trainer) == []
    finally:
        services._locks.remove(lock)
