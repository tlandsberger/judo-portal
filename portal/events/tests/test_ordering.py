"""Reihenfolge von Katalogwerten per Pfeil in der Liste."""

from __future__ import annotations

import pytest
from django.urls import reverse

from portal.events.models import EventType, ParticipantRole
from portal.members.models import Interest

from .conftest import PASSWORD

pytestmark = pytest.mark.django_db


def names(model) -> list[str]:
    return list(model.objects.values_list("name", flat=True))


def login(client, user):
    assert client.login(email=user.email, password=PASSWORD)
    return client


def test_arrows_move_one_step_and_stop_at_the_edge(client, head):
    login(client, head)
    first, second, *_ = ParticipantRole.objects.all()
    response = client.post(reverse("role_reorder"), {"down": first.pk}, follow=True)
    assert response.redirect_chain[-1][0].endswith(f"#sort-{first.pk}")
    assert f"„{first.name}“ nach unten verschoben." in response.content.decode()
    assert names(ParticipantRole)[:2] == [second.name, first.name]
    client.post(reverse("role_reorder"), {"up": second.pk})
    response = client.post(reverse("role_reorder"), {"up": second.pk}, follow=True)
    assert "verschoben" not in response.content.decode()
    assert names(ParticipantRole)[0] == second.name


def test_list_shows_arrows_form_has_no_order_field(client, head):
    login(client, head)
    page = client.get(reverse("role_list")).content.decode()
    assert 'form="reihenfolge"' in page and "nach oben" in page
    assert 'name="order"' not in client.get(reverse("role_create")).content.decode()
    assert 'name="order"' not in client.get(reverse("event_type_create")).content.decode()


def test_new_entries_go_to_the_end(client, head):
    login(client, head)
    client.post(reverse("event_type_create"), {"name": "Ausflug", "is_active": "on"})
    assert names(EventType)[-1] == "Ausflug"
    Interest.objects.create(name="Kata")
    Interest.objects.create(name="Breitensport")
    assert names(Interest) == ["Kata", "Breitensport"]


def test_only_heads_may_sort(client, parent, trainer):
    first = EventType.objects.first()
    for user in (parent, trainer):
        login(client, user)
        assert client.post(reverse("event_type_reorder"), {"down": first.pk}).status_code == 403
        client.logout()
    assert client.post(reverse("interest_reorder"), {"down": 1}).status_code == 302
    assert EventType.objects.first() == first


def test_interests_can_be_sorted(client, head):
    login(client, head)
    Interest.objects.create(name="Kata")
    wettkampf = Interest.objects.create(name="Wettkampf")
    assert "nach unten" in client.get(reverse("interest_list")).content.decode()
    client.post(reverse("interest_reorder"), {"up": wettkampf.pk})
    assert names(Interest) == ["Wettkampf", "Kata"]
    response = client.post(reverse("interest_list"), {"name": "Randori"}, follow=True)
    assert response.status_code == 200 and names(Interest)[-1] == "Randori"


def test_event_type_list_shows_saved_order(client, head):
    """Die Liste zählt Veranstaltungen (GROUP BY); Meta.ordering gilt dort nicht, die View sortiert selbst."""
    login(client, head)
    training, wettkampf = EventType.objects.get(name="Training"), EventType.objects.get(name="Wettkampf")
    client.post(reverse("event_type_reorder"), {"up": wettkampf.pk})
    page = client.get(reverse("event_type_list")).content.decode()
    assert page.index(f"sort-{wettkampf.pk}") < page.index(f"sort-{training.pk}")
