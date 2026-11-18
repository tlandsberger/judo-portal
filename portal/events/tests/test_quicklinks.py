"""Schnellzugang per Code, Quick-Link und QR-Code (ADR 0020)."""

from __future__ import annotations

import pytest
from django.conf import settings
from django.urls import reverse

from portal.events import quicklinks, services
from portal.events.models import Event, QuickLink

from .conftest import PASSWORD, make_occurrence, role

pytestmark = pytest.mark.django_db


def login(client, user):
    assert client.login(email=user.email, password=PASSWORD)
    return client


def test_code_is_created_once_and_easy_to_type():
    occurrence = make_occurrence()
    code = quicklinks.code_for(occurrence)
    assert len(code) == 6 and set(code) <= set(quicklinks.ALPHABET)
    assert not set(code) & set("01OIL")
    assert quicklinks.code_for(occurrence) == code
    assert quicklinks.code_for(occurrence.event) != code
    assert QuickLink.objects.count() == 2
    assert quicklinks.resolve(f" {code[:3].lower()}-{code[3:]} ").occurrence == occurrence
    assert quicklinks.resolve("") is None and quicklinks.resolve("XXXXXX") is None
    assert quicklinks.url(code) == f"{settings.BASE_URL}/q/{code}/"


def test_quick_link_needs_login_and_leads_to_target(client, parent, child):
    occurrence = make_occurrence()
    code = quicklinks.code_for(occurrence)
    response = client.get(reverse("quick_link", args=[code]))
    assert response.status_code == 302 and "/anmeldung/login/" in response["Location"]
    assert f"next=/q/{code}/" in response["Location"]
    login(client, parent)
    assert client.get(reverse("quick_link", args=[code.lower()]))["Location"] == reverse(
        "occurrence_detail", args=[occurrence.pk]
    )
    event_code = quicklinks.code_for(occurrence.event)
    target = client.get(reverse("quick_link_form"), {"code": event_code})["Location"]
    assert target == f"{reverse('agenda')}?f=1&veranstaltung={occurrence.event.pk}"
    page = client.get(target).content.decode()
    assert reverse("occurrence_detail", args=[occurrence.pk]) in page


def test_unknown_code(client, parent):
    login(client, parent)
    response = client.get(reverse("quick_link_form"), {"code": "ZZZZZZ"}, follow=True)
    assert "Code nicht gefunden." in response.content.decode()


def test_qr_codes_and_display_only_for_lead_and_heads(client, head, trainer, parent, child):
    occurrence = make_occurrence(Event.objects.create(title="Lehrgang"))
    services.set_team(occurrence, services.own_member(trainer), role("Trainer"))
    login(client, parent)
    page = client.get(reverse("occurrence_detail", args=[occurrence.pk])).content.decode()
    assert "Schnellzugang" not in page
    assert client.get(reverse("occurrence_qr", args=[occurrence.pk, "svg"])).status_code == 403
    client.logout()
    login(client, trainer)
    page = client.get(reverse("occurrence_detail", args=[occurrence.pk])).content.decode()
    code = QuickLink.objects.get(occurrence=occurrence).code
    assert "Schnellzugang" in page and code in page and quicklinks.url(code) in page
    svg = client.get(reverse("occurrence_qr", args=[occurrence.pk, "svg"]))
    assert svg["Content-Type"] == "image/svg+xml" and b"<svg" in svg.content
    png = client.get(reverse("occurrence_qr", args=[occurrence.pk, "png"]), {"download": ""})
    assert png.content.startswith(b"\x89PNG")
    assert png["Content-Disposition"] == f'attachment; filename="qr-termin-{code}.png"'
    assert client.get(reverse("occurrence_qr", args=[occurrence.pk, "gif"])).status_code == 404
    assert client.get(reverse("event_qr", args=[occurrence.event.pk, "svg"])).status_code == 403
    client.logout()
    login(client, head)
    page = client.get(reverse("event_detail", args=[occurrence.event.pk])).content.decode()
    assert quicklinks.code_for(occurrence.event) in page
    assert client.get(reverse("event_qr", args=[occurrence.event.pk, "png"])).status_code == 200
