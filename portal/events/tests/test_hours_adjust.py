"""„Anpassen“ der Stunden: Dauer, Rolle oder Übungsleiter in einem Formular; am Termin nichts mehr zu bestätigen."""

from __future__ import annotations

import pytest
from django.urls import reverse

from portal.events import services
from portal.events.models import Participation

from .conftest import PASSWORD, make_occurrence, make_trainer, role

pytestmark = pytest.mark.django_db


@pytest.fixture
def past(trainer):
    occurrence = make_occurrence(in_days=-1, hours=1.5)
    return services.set_team(occurrence, services.own_member(trainer), role("Trainer"))


def login(client, user):
    assert client.login(email=user.email, password=PASSWORD)
    return client


def url(participation, next_="/abrechnung/"):
    return reverse("hours_adjust", args=[participation.occurrence_id]) + f"?next={next_}"


def test_occurrence_page_has_no_confirmation_anymore(client, trainer, past):
    page = login(client, trainer).get(reverse("occurrence_detail", args=[past.occurrence_id])).content.decode()
    assert reverse("hours_confirm", args=[past.occurrence_id]) not in page
    assert reverse("hours_unconfirm", args=[past.occurrence_id]) not in page
    assert "noch nicht bestätigt" in page and reverse("billing_index") in page


def test_form_confirms_with_other_duration_and_role(client, trainer, past):
    login(client, trainer)
    response = client.get(url(past))
    assert response.context["form"].initial == {"member": past.member_id, "role": past.role_id, "minutes": 90}
    assert [r.name for r in response.context["form"].fields["role"].queryset] == ["Trainer", "Co-Trainer"]
    response = client.post(url(past), {"member": past.member_id, "role": role("Co-Trainer").pk, "minutes": 75})
    assert response.url == "/abrechnung/"
    past.refresh_from_db()
    assert past.role == role("Co-Trainer") and past.is_confirmed and past.minutes == 75
    # Bestätigte Zeile über den Stift wieder öffnen und ändern
    response = client.post(url(past), {"member": past.member_id, "role": role("Trainer").pk, "minutes": 80})
    past.refresh_from_db()
    assert past.role == role("Trainer") and past.minutes == 80


def test_substitute_confirms_own_hours(client, trainer, past):
    ben = services.own_member(make_trainer("ben@example.org", "Ben"))
    login(client, trainer)
    response = client.post(url(past), {"member": ben.pk, "role": past.role_id, "minutes": 30})
    assert response.url == "/abrechnung/"
    substitute = Participation.objects.get(occurrence=past.occurrence, member=ben)
    assert not substitute.is_confirmed and substitute.role == role("Trainer")
    assert not Participation.objects.filter(pk=past.pk, status__in=services.ACTIVE).exists()


def test_only_own_started_billable_participations(client, trainer, past):
    coming = services.set_team(make_occurrence(in_days=2), services.own_member(trainer), role("Trainer"))
    login(client, trainer)
    response = client.get(url(coming))
    assert response.url == "/abrechnung/"
    login(client, make_trainer("ben@example.org", "Ben"))
    assert client.get(url(past)).status_code == 404


def test_start_page_and_month_link_to_the_form(client, trainer, past):
    login(client, trainer)
    assert reverse("hours_adjust", args=[past.occurrence_id]) in client.get("/").content.decode()
    services.confirm(past)
    month = past.occurrence.starts_at
    page = client.get(reverse("billing_month", args=[month.year, month.month])).content.decode()
    assert reverse("hours_adjust", args=[past.occurrence_id]) in page
    assert 'name="minutes"' not in page  # kein Eingabefeld mehr in der Tabelle
