"""Vertretungen (ADR 0018): übertragen, vertreten, austragen – vor dem Termin und nachträglich („Nicht dabei?“)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from portal.events import notices, services
from portal.events.models import Participation, ParticipationStatus
from portal.events.services import RegistrationError
from portal.notifications.models import SentNotification
from portal.notifications.services import Action

from .conftest import make_occurrence, make_trainer, role

pytestmark = pytest.mark.django_db


@pytest.fixture
def run(django_capture_on_commit_callbacks):
    def runner(job, *args, **kwargs):
        with django_capture_on_commit_callbacks(execute=True):
            return job(*args, **kwargs)

    return runner


@pytest.fixture
def shift(trainer):
    """Anna war gestern als Trainerin eingeteilt."""
    occurrence = make_occurrence(in_days=-1)
    return services.set_team(occurrence, services.own_member(trainer), role("Trainer"))


@pytest.fixture
def upcoming(trainer):
    """Anna ist übermorgen als Trainerin eingeteilt."""
    return services.set_team(make_occurrence(in_days=2), services.own_member(trainer), role("Trainer"))


@pytest.fixture
def ben_user(db):
    return make_trainer("ben@example.org", "Ben")


# Nachträglich


def test_withdraw_after_the_fact_even_if_confirmed(shift, trainer):
    services.confirm(shift, 60)
    services.withdraw(shift, trainer)
    assert not Participation.objects.filter(pk=shift.pk).exists()


def test_others_may_not_undo_confirmed_hours(shift, head):
    services.confirm(shift, 60)
    with pytest.raises(RegistrationError, match="schon Stunden bestätigt"):
        services.withdraw(shift, head)


def test_hand_over_afterwards_asks_substitute_to_confirm_once(shift, trainer, ben_user, run):
    ben = services.own_member(ben_user)
    substitute = run(services.hand_over, shift, ben, role("Co-Trainer"), trainer)
    assert substitute.member == ben and substitute.role.name == "Co-Trainer"
    assert not Participation.objects.filter(pk=shift.pk).exists()
    sent = SentNotification.objects.get(user=ben_user)
    assert sent.kind == "confirm"
    # Die Abend-Erinnerung nutzt denselben Schlüssel und kommt nicht noch einmal.
    run(notices.notify_confirm_hours)
    assert SentNotification.objects.filter(user=ben_user).count() == 1
    with pytest.raises(RegistrationError, match="schon als Co-Trainer"):
        anna_again = services.set_team(shift.occurrence, services.own_member(trainer), role("Trainer"))
        services.hand_over(anna_again, ben, role("Trainer"), trainer)


def test_cancel_after_without_notices_and_blocked_by_others(shift, trainer, child, ben_user, run):
    occurrence = shift.occurrence
    Participation.objects.create(
        occurrence=occurrence, member=child, role=role("Teilnehmer"), status=ParticipationStatus.REGISTERED
    )
    other = services.set_team(occurrence, services.own_member(ben_user), role("Co-Trainer"))
    services.confirm(other, 90)
    with pytest.raises(RegistrationError, match="Ben Trainer hat schon Stunden bestätigt"):
        services.cancel_after(occurrence, trainer)
    services.unconfirm(other)
    services.confirm(shift, 60)  # die eigene Bestätigung nimmt das Absagen selbst zurück
    run(services.cancel_after, occurrence, trainer)
    occurrence.refresh_from_db()
    shift.refresh_from_db()
    assert occurrence.is_cancelled and not shift.is_confirmed
    assert not SentNotification.objects.filter(kind="cancelled").exists()


def test_cancel_menu_after_start_cancels_without_notices(client, shift, trainer):
    client.force_login(trainer)
    page = client.get(reverse("occurrence_detail", args=[shift.occurrence_id])).content.decode()
    assert "Hat nicht stattgefunden" in page and "Termin absagen" not in page
    client.post(reverse("occurrence_cancel", args=[shift.occurrence_id]))
    shift.occurrence.refresh_from_db()
    assert shift.occurrence.is_cancelled
    assert not SentNotification.objects.filter(kind="cancelled").exists()


def test_confirm_reminder_offers_absent_button(shift, monkeypatch):
    seen: list[list[Action]] = []
    monkeypatch.setattr(
        notices.notifications, "notify", lambda user, **kwargs: seen.append(list(kwargs["actions"])) or True
    )
    notices.notify_confirm_hours(timezone.now() + timedelta(days=1))
    [actions] = seen
    assert [a.title for a in actions] == ["Bestätigen", "Nicht dabei?"]
    assert actions[1].url == reverse("occurrence_detail", args=[shift.occurrence_id]) + "#h-team"


def test_old_absent_url_redirects_to_occurrence(client, shift, trainer):
    """Altlast: Links aus älteren Erinnerungen führen zum Termin."""
    client.force_login(trainer)
    response = client.get(reverse("hours_absent", args=[shift.occurrence_id]))
    assert response.status_code == 301
    assert response.url == reverse("occurrence_detail", args=[shift.occurrence_id]) + "#h-team"


# Vor dem Termin


def test_hand_over_before_start_notifies_substitute(upcoming, trainer, ben_user, run):
    ben = services.own_member(ben_user)
    substitute = run(services.hand_over, upcoming, ben, None, trainer)
    assert substitute.role.name == "Trainer" and substitute.member == ben
    sent = SentNotification.objects.get(user=ben_user)
    assert sent.kind == "hand_over"
    assert not SentNotification.objects.filter(user=trainer).exists()  # wer selbst handelt, bekommt nichts


def test_take_over_notifies_the_one_who_is_replaced(
    client, upcoming, trainer, ben_user, django_capture_on_commit_callbacks
):
    client.force_login(ben_user)
    url = reverse("occurrence_detail", args=[upcoming.occurrence_id])
    page = client.get(url).content.decode()
    assert "Anna Trainer vertreten" in page
    assert reverse("occurrence_hand_over", args=[upcoming.occurrence_id, upcoming.pk]) not in page
    with django_capture_on_commit_callbacks(execute=True):
        client.post(reverse("occurrence_take_over", args=[upcoming.occurrence_id, upcoming.pk]))
    team = services.team(upcoming.occurrence)
    assert [(p.member.first_name, p.role.name) for p in team] == [("Ben", "Trainer")]
    assert SentNotification.objects.get(user=trainer).kind == "hand_over"
    assert not SentNotification.objects.filter(user=ben_user).exists()


def test_take_over_needs_the_role(client, upcoming, parent):
    """Eltern ohne Übungsleiter-Rolle können nicht vertreten."""
    from portal.members.models import LinkKind, MemberLink

    from .conftest import make_member

    MemberLink.objects.create(user=parent, member=make_member("Paul", age=40), kind=LinkKind.SELF)
    client.force_login(parent)
    client.post(reverse("occurrence_take_over", args=[upcoming.occurrence_id, upcoming.pk]))
    assert Participation.objects.filter(pk=upcoming.pk).exists()


def test_hand_over_page(client, upcoming, trainer, ben_user, django_capture_on_commit_callbacks):
    client.force_login(trainer)
    url = reverse("occurrence_hand_over", args=[upcoming.occurrence_id, upcoming.pk])
    page = client.get(url).content.decode()
    assert "Wer übernimmt?" in page and "Ben Trainer" in page and "Anna Trainer</option>" not in page
    ben = services.own_member(ben_user)
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(url, {"member": ben.pk, "role": upcoming.role_id})
    assert response.url == reverse("occurrence_detail", args=[upcoming.occurrence_id])
    assert services.team(upcoming.occurrence)[0].member == ben


def test_hand_over_only_own_or_as_lead(client, upcoming, ben_user):
    client.force_login(ben_user)
    assert client.get(reverse("occurrence_hand_over", args=[upcoming.occurrence_id, upcoming.pk])).status_code == 403


def test_additional_trainer_and_withdraw_without_substitute(client, upcoming, ben_user):
    """Zusätzlich eintragen und ohne Vertretung austragen : keine Rückfrage, solange ein Trainer bleibt."""
    client.force_login(ben_user)
    client.post(reverse("occurrence_team", args=[upcoming.occurrence_id]), {"role": role("Co-Trainer").pk})
    co = Participation.objects.get(occurrence=upcoming.occurrence, member=services.own_member(ben_user))
    response = client.post(reverse("occurrence_team_remove", args=[upcoming.occurrence_id, co.pk]))
    assert response.status_code == 302
    assert not Participation.objects.filter(pk=co.pk).exists()


# Kein Trainer mehr


def test_last_trainer_is_asked_and_heads_are_informed(
    client, upcoming, trainer, head, django_capture_on_commit_callbacks
):
    client.force_login(trainer)
    url = reverse("occurrence_team_remove", args=[upcoming.occurrence_id, upcoming.pk])
    page = client.post(url).content.decode()
    assert "kein Trainer mehr eingeteilt" in page
    assert Participation.objects.filter(pk=upcoming.pk).exists()
    with django_capture_on_commit_callbacks(execute=True):
        client.post(url, {"confirmed": "1"})
    assert not Participation.objects.filter(pk=upcoming.pk).exists()
    upcoming.occurrence.refresh_from_db()
    assert upcoming.occurrence.trainer_missing_since is not None
    assert SentNotification.objects.get(user=head).kind == "trainer_missing"


def test_heads_are_reminded_two_days_before(upcoming, trainer, head, ben_user, run):
    run(services.withdraw, upcoming, trainer)
    occurrence = upcoming.occurrence
    starts = occurrence.starts_at
    run(notices.notify_trainer_missing, starts - timedelta(days=3))
    assert SentNotification.objects.filter(user=head).count() == 1  # nur die Sofort-Nachricht
    run(notices.notify_trainer_missing, starts - timedelta(days=1))
    run(notices.notify_trainer_missing, starts - timedelta(hours=20))
    assert SentNotification.objects.filter(user=head, key__startswith="trainer-missing-reminder").count() == 1


def test_no_reminder_once_someone_steps_in(upcoming, trainer, head, ben_user, run):
    run(services.withdraw, upcoming, trainer)
    services.set_team(upcoming.occurrence, services.own_member(ben_user), role("Trainer"))
    upcoming.occurrence.refresh_from_db()
    assert upcoming.occurrence.trainer_missing_since is None
    run(notices.notify_trainer_missing, upcoming.occurrence.starts_at - timedelta(days=1))
    assert not SentNotification.objects.filter(key__startswith="trainer-missing-reminder").exists()
