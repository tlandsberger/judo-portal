from __future__ import annotations

from datetime import time, timedelta
from decimal import Decimal

import pytest
from django.core import mail
from django.utils import timezone

from portal.events import services
from portal.events.models import Event, ParticipationStatus, Schedule, TargetGroup, TargetMode
from portal.events.services import RegistrationError
from portal.members.models import LinkKind, MemberLink
from portal.notifications.models import SentNotification

from .conftest import event_type, make_member, make_occurrence, make_user, role

pytestmark = pytest.mark.django_db


def test_register_and_unregister(child, parent):
    occurrence = make_occurrence()
    registration = services.register(occurrence, child, parent, note="komme später")
    assert registration.status == ParticipationStatus.REGISTERED
    assert registration.registered_by == parent
    services.unregister(registration, parent)
    assert registration.status == ParticipationStatus.CANCELLED
    assert services.register(occurrence, child, parent).status == ParticipationStatus.REGISTERED


def test_target_group_blocks_registration(child, parent):
    event = Event.objects.create(title="Erwachsene")
    TargetGroup.objects.create(event=event, name="Erwachsene", min_age=18)
    with pytest.raises(
        RegistrationError, match=r"^Mia gehört leider nicht zur Zielgruppe dieses Termins\. Anmeldung nur"
    ):
        services.register(make_occurrence(event), child, parent)


def test_own_profile_gets_du_in_hint(trainer):
    event = Event.objects.create(title="Kinder")
    TargetGroup.objects.create(event=event, max_age=12)
    with pytest.raises(RegistrationError, match=r"^Du gehörst leider nicht"):
        services.register(make_occurrence(event), services.own_member(trainer), trainer)


def test_recommendation_allows_registration_and_tells_team(
    child, parent, trainer, head, django_capture_on_commit_callbacks
):
    event = Event.objects.create(title="Erwachsene", target_mode=TargetMode.RECOMMENDED)
    TargetGroup.objects.create(event=event, min_age=18)
    occurrence = make_occurrence(event)
    services.set_team(occurrence, services.own_member(trainer), role("Trainer"))
    with django_capture_on_commit_callbacks(execute=True):
        registration = services.register(occurrence, child, parent)
    assert registration.status == ParticipationStatus.REGISTERED and registration.off_target
    sent = SentNotification.objects.filter(kind="off_target")
    assert [n.user for n in sent] == [trainer]  # nicht die Abteilungsleitung, es gibt Übungsleiter
    assert sent[0].title == "Anmeldung außerhalb der Zielgruppe"
    assert any("Mia Muster hat sich für Erwachsene" in m.body for m in mail.outbox)


def test_off_target_without_team_goes_to_heads(child, parent, head, django_capture_on_commit_callbacks):
    event = Event.objects.create(title="Erwachsene", target_mode=TargetMode.RECOMMENDED)
    TargetGroup.objects.create(event=event, min_age=18)
    with django_capture_on_commit_callbacks(execute=True):
        services.register(make_occurrence(event), child, parent)
    assert [n.user for n in SentNotification.objects.filter(kind="off_target")] == [head]


def test_matching_registration_is_not_off_target(child, parent, head, django_capture_on_commit_callbacks):
    event = Event.objects.create(title="Kinder", target_mode=TargetMode.RECOMMENDED)
    TargetGroup.objects.create(event=event, max_age=12)
    with django_capture_on_commit_callbacks(execute=True):
        assert not services.register(make_occurrence(event), child, parent).off_target
    assert not SentNotification.objects.filter(kind="off_target").exists()


def test_occurrence_target_groups_override_event(child, parent, head):
    event = Event.objects.create(title="Training")
    TargetGroup.objects.create(event=event, name="Erwachsene", min_age=18)
    occurrence = make_occurrence(event)
    assert services.match_occurrence(occurrence, child) == services.Match.NO
    services.customize_target_groups(occurrence, head)
    occurrence.refresh_from_db()
    assert occurrence.custom_target_groups and occurrence.is_modified
    [group] = occurrence.target_groups.all()
    assert group.name == "Erwachsene" and group.min_age == 18  # Kopie der Veranstaltung
    group.min_age = None
    group.max_age = 12
    group.save()
    assert services.match_occurrence(occurrence, child) == services.Match.YES
    assert services.register(occurrence, child, parent).status == ParticipationStatus.REGISTERED
    other = make_occurrence(event, in_days=10)
    assert services.match_occurrence(other, child) == services.Match.NO  # nur dieser Termin
    services.reset_target_groups(occurrence, head)
    occurrence.refresh_from_db()
    assert not occurrence.custom_target_groups and not occurrence.target_groups.exists()
    assert services.match_occurrence(occurrence, child) == services.Match.NO


def test_custom_target_groups_survive_regenerate(head):
    event = Event.objects.create(title="Training")
    today = timezone.localdate()
    schedule = Schedule.objects.create(
        event=event,
        weekday=(today + timedelta(days=2)).weekday(),
        start_time=time(17),
        end_time=time(18),
        valid_from=today,
    )
    services.generate(schedule)
    occurrence = schedule.occurrences.first()
    services.customize_target_groups(occurrence, head)
    schedule.start_time = time(16)
    schedule.save()
    services.regenerate(schedule)
    occurrence.refresh_from_db()
    assert occurrence.custom_target_groups


def test_exception_ignores_target_group_window_and_capacity(child, trainer):
    event = Event.objects.create(title="Kader", capacity=0)
    TargetGroup.objects.create(event=event, name="Erwachsene", min_age=18)
    occurrence = make_occurrence(event, in_days=-0.01)
    registration = services.register(occurrence, child, trainer, exception=True)
    assert registration.status == ParticipationStatus.REGISTERED
    assert registration.exception_by == trainer


def test_fixed_registration_window(child, parent):
    now = timezone.now()
    occurrence = make_occurrence(
        Event.objects.create(title="Wettkampf"),
        in_days=10,
        registration_opens_at=now + timedelta(days=1),
        registration_closes_at=now + timedelta(days=5),
    )
    assert services.window(occurrence) == "before"
    with pytest.raises(RegistrationError, match="öffnet am"):
        services.register(occurrence, child, parent)
    assert services.window(occurrence, now + timedelta(days=2)) == "open"
    assert services.window(occurrence, now + timedelta(days=6)) == "closed"


def test_no_unregister_after_deadline_except_force(child, parent, trainer):
    event = Event.objects.create(title="Wettkampf")
    occurrence = make_occurrence(event)
    registration = services.register(occurrence, child, parent)
    occurrence.registration_closes_at = timezone.now() - timedelta(minutes=1)
    occurrence.save()
    with pytest.raises(RegistrationError, match="Anmeldeschluss"):
        services.unregister(registration, parent)
    services.unregister(registration, trainer, force=True)
    assert registration.status == ParticipationStatus.CANCELLED


def test_cancelled_occurrence_blocks(child, parent):
    occurrence = make_occurrence()
    services.cancel(occurrence)
    with pytest.raises(RegistrationError, match="abgesagt"):
        services.register(occurrence, child, parent)


def test_waitlist_and_promotion_with_mail(child, parent, django_capture_on_commit_callbacks):
    other_parent = make_user("zwei@example.org")
    other = make_member("Ben", age=10)
    MemberLink.objects.create(user=other_parent, member=other, kind=LinkKind.GUARDIAN)
    occurrence = make_occurrence(Event.objects.create(title="Lehrgang", event_type=event_type("Lehrgang"), capacity=1))
    first = services.register(occurrence, child, parent)
    second = services.register(occurrence, other, other_parent)
    assert second.status == ParticipationStatus.WAITLIST
    with django_capture_on_commit_callbacks(execute=True):
        services.unregister(first, parent)
    second.refresh_from_db()
    assert second.status == ParticipationStatus.REGISTERED
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


def test_agenda_lists_each_occurrence_once_for_two_children(parent, child):
    kids = Event.objects.create(title="Kindertraining")
    adults = Event.objects.create(title="Erwachsenentraining")
    TargetGroup.objects.create(event=adults, name="Erwachsene", min_age=18)
    make_occurrence(kids)
    make_occurrence(adults)
    sibling = make_member("Ole", age=7)
    MemberLink.objects.create(user=parent, member=sibling, kind=LinkKind.GUARDIAN)
    result = services.agenda(parent)
    assert result.several and result.has_members
    [entry] = result.entries
    assert entry.occurrence.event.title == "Kindertraining"
    assert [row.member.first_name for row in entry.rows] == ["Mia", "Ole"]
    assert all(row.item.can_register for row in entry.rows)
    assert [e.occurrence for e in services.next_entries(parent)] == [entry.occurrence]
    everything = services.agenda(parent, services.AgendaFilter(matching=False))
    assert [e.occurrence.event.title for e in everything.entries] == ["Kindertraining", "Erwachsenentraining"]
    assert not any(row.item.can_register for row in everything.entries[1].rows)


def test_agenda_shows_all_upcoming_not_only_six_weeks(parent, child):
    later = make_occurrence(in_days=200)
    make_occurrence(in_days=-2)
    assert [e.occurrence for e in services.agenda(parent).entries] == [later]


def test_agenda_filters(parent, child):
    training = Event.objects.create(title="Training", event_type=event_type("Training"))
    contest = Event.objects.create(title="Turnier", event_type=event_type("Wettkampf"))
    mine = make_occurrence(training, in_days=2)
    cancelled = make_occurrence(training, in_days=4)
    services.cancel(cancelled, notify=False)
    closed = make_occurrence(contest, in_days=6, registration_closes_at=timezone.now())
    adults = Event.objects.create(title="Erwachsene", event_type=event_type("Wettkampf"))
    TargetGroup.objects.create(event=adults, min_age=18)
    other = make_occurrence(adults, in_days=8)
    make_occurrence(training, in_days=-10)
    services.register(mine, child, parent)

    def titles(**kwargs):
        return [e.occurrence for e in services.agenda(parent, services.AgendaFilter(**kwargs)).entries]

    assert titles() == [mine, cancelled, closed]  # „Für mich“
    assert titles(matching=False) == [mine, cancelled, closed, other]
    assert titles(event=training.pk) == [mine, cancelled]
    assert titles(hide_cancelled=True) == [mine, closed]
    assert titles(mine=True) == [mine]  # „Nur angemeldete“
    assert titles(no_training=True) == [closed]  # „Ohne Trainings“
    assert titles(matching=False, no_training=True) == [closed, other]
    assert titles(mine=True, no_training=True) == []  # UND


def test_agenda_without_own_members_lists_everything(head):
    adults = Event.objects.create(title="Erwachsene")
    TargetGroup.objects.create(event=adults, min_age=18)
    occurrence = make_occurrence(adults)
    result = services.agenda(head)
    assert not result.has_members
    assert [(e.occurrence, e.rows) for e in result.entries] == [(occurrence, [])]
    assert services.next_entries(head) == []


def test_guardian_link_ends_at_18(parent):
    grown = make_member("Lea", age=18)
    MemberLink.objects.create(user=parent, member=grown, kind=LinkKind.GUARDIAN)
    make_occurrence()
    assert not services.agenda(parent).has_members
