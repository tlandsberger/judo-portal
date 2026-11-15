"""Benachrichtigungen rund um Termine (ohne Push-Gerät landen sie per Mail)."""

from __future__ import annotations

from datetime import datetime, time, timedelta

import pytest
from django.core import mail
from django.utils import timezone

from portal.events import notices, services
from portal.events.models import Event, EventKind, RegistrationStatus, StaffFunction, Staffing, TargetGroup
from portal.members.models import LinkKind, MemberLink
from portal.notifications import services as notifications
from portal.notifications.models import SentNotification
from portal.notifications.services import Action

from .conftest import make_member, make_occurrence, make_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def run(django_capture_on_commit_callbacks):
    """Führt einen Job aus und verschickt die Nachrichten (nach dem Commit)."""

    def runner(job, *args, **kwargs):
        with django_capture_on_commit_callbacks(execute=True):
            job(*args, **kwargs)

    return runner


def competition(**extra) -> Event:
    return Event.objects.create(title="Kinderwettkampf", kind=EventKind.COMPETITION, **extra)


def subjects() -> list[str]:
    return [m.subject.removeprefix("[Wedeler TSV Judo] ") for m in mail.outbox]


def test_registration_open_once_for_matching_members(run, parent, child):
    occurrence = make_occurrence(competition(), in_days=10)
    run(notices.notify_registration_open)
    run(notices.notify_registration_open)
    assert subjects() == ["Anmeldung offen: Kinderwettkampf"]
    assert mail.outbox[0].to == [parent.email]
    assert "Für Mia ist die Anmeldung" in mail.outbox[0].body
    assert SentNotification.objects.get().key == f"registration_open:{occurrence.pk}:{parent.pk}"


def test_registration_open_skips_training_registered_unmatched_and_closed(run, parent, child):
    make_occurrence(Event.objects.create(title="Training"), in_days=2)
    adults = competition()
    adults.target_groups.set([TargetGroup.objects.create(name="Erwachsene", min_age=18)])
    make_occurrence(adults, in_days=5)
    later = make_occurrence(competition(opens_days_before=3), in_days=10)
    registered = make_occurrence(competition(), in_days=6)
    services.register(registered, child, parent)
    run(notices.notify_registration_open)
    assert mail.outbox == []
    run(notices.notify_registration_open, now=later.starts_at - timedelta(days=2))
    assert subjects() == ["Anmeldung offen: Kinderwettkampf"]


def test_one_message_for_two_children_without_button(run, parent, child, monkeypatch):
    sibling = make_member("Ole", age=8)
    MemberLink.objects.create(user=parent, member=sibling, kind=LinkKind.GUARDIAN)
    make_occurrence(competition(), in_days=10)
    captured = []
    monkeypatch.setattr(notifications, "notify", lambda user, **kwargs: captured.append(kwargs) or True)
    notices.notify_registration_open()
    [message] = captured
    assert "Für Mia und Ole" in message["body"] or "Für Ole und Mia" in message["body"]
    assert message["actions"] == []


def test_register_button(parent, child):
    occurrence = make_occurrence(competition(), in_days=10)
    token = Action("register", "Anmelden", {"o": occurrence.pk, "m": child.pk}).token(parent)
    result = notifications.run_action(token)
    assert result.ok and "Mia ist für Kinderwettkampf angemeldet" in result.message
    assert occurrence.registrations.get().status == RegistrationStatus.REGISTERED
    # fremdes Kind, Pflichtgewicht, geschlossene Anmeldung
    stranger = make_user("fremd@example.org")
    assert not notifications.run_action(Action("register", "x", {"o": occurrence.pk, "m": child.pk}).token(stranger)).ok
    weighed = make_occurrence(competition(weight_required=True), in_days=10)
    result = notifications.run_action(Action("register", "x", {"o": weighed.pk, "m": child.pk}).token(parent))
    assert not result.ok and result.url.endswith(f"/anmelden/{child.pk}/")
    closed = make_occurrence(competition(registration_closes_at=timezone.now() - timedelta(hours=1)), in_days=10)
    result = notifications.run_action(Action("register", "x", {"o": closed.pk, "m": child.pk}).token(parent))
    assert not result.ok and "geschlossen" in result.message


def test_deadline_reminder(run, parent, child):
    closes = timezone.now() + timedelta(hours=20)
    occurrence = make_occurrence(competition(registration_closes_at=closes), in_days=10)
    run(notices.notify_registration_open)
    run(notices.notify_deadlines)
    assert subjects() == ["Anmeldung offen: Kinderwettkampf"]  # gerade erst informiert
    SentNotification.objects.update(created_at=timezone.now() - timedelta(hours=13))
    run(notices.notify_deadlines)
    run(notices.notify_deadlines)
    assert subjects()[1:] == ["Nur noch kurz: Kinderwettkampf"]
    assert "Mia ist noch nicht angemeldet" in mail.outbox[1].body
    services.register(occurrence, child, parent)
    assert len(mail.outbox) == 2


def test_confirm_staffing_reminder_in_the_evening(run, trainer):
    day = timezone.localdate() - timedelta(days=1)
    starts = timezone.make_aware(datetime.combine(day, time(17)))
    event = Event.objects.create(title="Training")
    occurrence = event.occurrences.create(starts_at=starts, ends_at=starts + timedelta(hours=1, minutes=30))
    staffing = Staffing.objects.create(occurrence=occurrence, user=trainer, function=StaffFunction.TRAINER)
    run(notices.notify_confirm_staffing, now=starts + timedelta(hours=2))  # 19 Uhr: noch nicht
    assert mail.outbox == []
    run(notices.notify_confirm_staffing, now=starts + timedelta(hours=3, minutes=5))
    assert subjects() == ["Begleitung bestätigen"]
    result = notifications.run_action(Action("confirm", "Bestätigen", {"s": staffing.pk}).token(trainer))
    assert result.ok and "90 Minuten" in result.message
    staffing.refresh_from_db()
    assert staffing.is_confirmed


def test_confirm_due_for_late_occurrence():
    late = timezone.make_aware(datetime(2026, 11, 20, 21, 0))
    assert timezone.localtime(notices.confirm_due(late)).hour == 8
    assert timezone.localtime(notices.confirm_due(late)).day == 21


def test_changed_notifies_participants_and_team_but_not_editor(run, parent, child, trainer, head):
    occurrence = make_occurrence(in_days=4)
    services.register(occurrence, child, parent)
    Staffing.objects.create(occurrence=occurrence, user=trainer, function=StaffFunction.TRAINER)
    occurrence.location = "Turnhalle Nord"
    run(services.update_occurrence, occurrence, ["location"], trainer)
    assert sorted(m.to[0] for m in mail.outbox) == [parent.email]
    assert "Turnhalle Nord" in mail.outbox[0].body
    occurrence.note = "Bitte Gürtel mitbringen"
    run(services.update_occurrence, occurrence, ["note"], head)
    assert len(mail.outbox) == 1  # nur der Hinweis: keine Nachricht


def test_promoted_button_unregisters(parent, child, django_capture_on_commit_callbacks):
    other_parent = make_user("zwei@example.org")
    other = make_member("Ben")
    MemberLink.objects.create(user=other_parent, member=other, kind=LinkKind.GUARDIAN)
    occurrence = make_occurrence(Event.objects.create(title="Lehrgang", kind=EventKind.COURSE, capacity=1))
    first = services.register(occurrence, other, other_parent)
    second = services.register(occurrence, child, parent)
    with django_capture_on_commit_callbacks(execute=True):
        services.unregister(first, other_parent)
    assert subjects() == ["Nachgerückt: Lehrgang"]
    result = notifications.run_action(Action("unregister", "Doch absagen", {"r": second.pk}).token(parent))
    assert result.ok
    second.refresh_from_db()
    assert second.status == RegistrationStatus.CANCELLED
    assert not notifications.run_action(Action("unregister", "x", {"r": second.pk}).token(other_parent)).ok
