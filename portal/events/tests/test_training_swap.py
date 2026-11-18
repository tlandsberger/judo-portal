"""Trainingstausch: alle Trainings eines Tages mit Übungsleitern, Vertreten/Übertragen/Entfernen zurück zum Tag."""

from __future__ import annotations

import pytest
from django.urls import reverse
from django.utils import timezone

from portal.events import services
from portal.events.models import Event, Participation

from .conftest import PASSWORD, event_type, make_occurrence, make_trainer, role

pytestmark = pytest.mark.django_db


def login(client, user):
    assert client.login(email=user.email, password=PASSWORD)
    return client


def day_of(occurrence) -> str:
    return timezone.localtime(occurrence.starts_at).date().isoformat()


@pytest.fixture
def training(trainer):
    """Übermorgen ein Training mit Anna als Trainerin."""
    occurrence = make_occurrence(
        Event.objects.create(title="Kindertraining", event_type=event_type("Training")), in_days=2
    )
    services.set_team(occurrence, services.own_member(trainer), role("Trainer"))
    return occurrence


def test_lists_only_trainings_of_the_day_with_actions(client, training, trainer):
    contest = Event.objects.create(title="Turnier", event_type=event_type("Wettkampf"))
    make_occurrence(contest, in_days=2)
    ben = make_trainer("ben@example.org", "Ben")
    login(client, ben)
    page = client.get(reverse("training_swap"), {"tag": day_of(training)}).content.decode()
    assert "Kindertraining" in page and "Turnier" not in page
    assert "Anna Trainer" in page and "Anna Trainer vertreten" in page
    assert "Platz von Anna Trainer übertragen" not in page  # nur für sich selbst oder wer den Termin leitet
    login(client, trainer)
    page = client.get(reverse("training_swap"), {"tag": day_of(training)}).content.decode()
    assert "Meinen Platz übertragen" in page and "Mich entfernen" in page
    assert (
        "An diesem Tag ist kein Training."
        in client.get(reverse("training_swap"), {"tag": "2001-01-01"}).content.decode()
    )


def test_actions_return_to_the_day(client, training, trainer):
    ben = make_trainer("ben@example.org", "Ben")
    back = f"{reverse('training_swap')}?tag={day_of(training)}"
    [anna] = services.team(training)
    login(client, ben)
    response = client.post(reverse("occurrence_take_over", args=[training.pk, anna.pk]), {"next": back})
    assert response.url == back
    [ben_shift] = services.team(training)
    assert ben_shift.member == services.own_member(ben)
    # Entfernen des letzten Trainers fragt nach und kommt danach auch zurück
    response = client.post(reverse("occurrence_team_remove", args=[training.pk, ben_shift.pk]), {"next": back})
    assert f'name="next" value="{back}"' in response.content.decode()
    response = client.post(
        reverse("occurrence_team_remove", args=[training.pk, ben_shift.pk]), {"next": back, "confirmed": "1"}
    )
    assert response.url == back and not Participation.objects.filter(pk=ben_shift.pk).exists()


def test_hand_over_returns_to_the_day(client, training, trainer):
    ben = make_trainer("ben@example.org", "Ben")
    back = f"{reverse('training_swap')}?tag={day_of(training)}"
    [anna] = services.team(training)
    login(client, trainer)
    url = reverse("occurrence_hand_over", args=[training.pk, anna.pk]) + "?next=" + back
    response = client.post(url, {"member": services.own_member(ben).pk, "role": anna.role_id})
    assert response.url == back


def test_only_for_trainers_and_heads(client, parent, head, trainer):
    login(client, parent)
    assert client.get(reverse("training_swap")).status_code == 403
    assert reverse("training_swap") not in client.get(reverse("home")).content.decode()
    for user in (trainer, head):
        login(client, user)
        assert client.get(reverse("training_swap")).status_code == 200
        assert reverse("training_swap") in client.get(reverse("home")).content.decode()


def test_unknown_day_falls_back_to_today(client, trainer):
    login(client, trainer)
    page = client.get(reverse("training_swap"), {"tag": "kaputt"}).content.decode()
    assert f'value="{timezone.localdate().isoformat()}"' in page
