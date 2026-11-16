"""„Nicht dabei?“: nachträglich austragen, an eine Vertretung übertragen, Termin nachträglich absagen (ADR 0012)."""

from __future__ import annotations

import pytest
from django.urls import reverse

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
    occurrence = make_occurrence(in_days=-1)
    return services.set_team(occurrence, services.own_member(trainer), role("Trainer"))


def test_withdraw_after_the_fact_even_if_confirmed(shift, trainer):
    services.confirm(shift, 60)
    services.withdraw(shift, trainer)
    assert not Participation.objects.filter(pk=shift.pk).exists()


def test_withdraw_only_after_start(trainer):
    future = services.set_team(make_occurrence(in_days=2), services.own_member(trainer), role("Trainer"))
    with pytest.raises(RegistrationError, match="Vor dem Termin"):
        services.withdraw(future, trainer)


def test_hand_over_to_substitute_who_is_notified_once(shift, trainer, run):
    ben_user = make_trainer("ben@example.org", "Ben")
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


def test_cancel_after_without_notices_and_blocked_by_others(shift, trainer, child, parent, run):
    occurrence = shift.occurrence
    Participation.objects.create(
        occurrence=occurrence, member=child, role=role("Teilnehmer"), status=ParticipationStatus.REGISTERED
    )
    ben = services.own_member(make_trainer("ben@example.org", "Ben"))
    other = services.set_team(occurrence, ben, role("Co-Trainer"))
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


def test_confirm_reminder_offers_absent_button(shift, trainer, run, monkeypatch):
    seen: list[list[Action]] = []
    monkeypatch.setattr(
        notices.notifications, "notify", lambda user, **kwargs: seen.append(list(kwargs["actions"])) or True
    )
    from datetime import timedelta

    from django.utils import timezone

    notices.notify_confirm_hours(timezone.now() + timedelta(days=1))
    [actions] = seen
    assert [a.title for a in actions] == ["Bestätigen", "Nicht dabei?"]
    assert actions[1].url == reverse("hours_absent", args=[shift.occurrence_id])


def test_absent_page(client, shift, trainer):
    client.force_login(trainer)
    url = reverse("hours_absent", args=[shift.occurrence_id])
    page = client.get(url).content.decode()
    assert "Ich wurde vertreten" in page and "nicht stattgefunden" in page
    client.post(url, {"what": "hand_over"})
    assert Participation.objects.filter(pk=shift.pk).exists()  # Vertretung fehlt
    client.post(url, {"what": "withdraw"})
    assert not Participation.objects.filter(pk=shift.pk).exists()


def test_absent_page_only_for_own_participation(client, shift):
    client.force_login(make_trainer("ben@example.org", "Ben"))
    assert client.get(reverse("hours_absent", args=[shift.occurrence_id])).status_code == 404
