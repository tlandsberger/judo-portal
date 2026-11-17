"""Seitenlayout (ADR 0017): einheitlicher Kopf, eine Hauptaktion in der Aktionsleiste, Menü „Weitere Aktionen“."""

from __future__ import annotations

import pytest
from django.template import Context, Template
from django.urls import reverse

from portal.accounts.models import Role
from portal.events.models import ParticipantRole
from portal.events.tests.conftest import PASSWORD, make_user

pytestmark = pytest.mark.django_db


def render(source: str, **context: object) -> str:
    return Template("{% load page %}" + source).render(Context(context))


def test_capture_sets_variable_and_ignores_whitespace():
    assert render("{% capture as x %}  \n {% endcapture %}[{{ x }}]") == "[]"
    assert render("{% capture as x %} <b>{{ name }}</b> {% endcapture %}[{{ x }}]", name="A&B") == "[<b>A&amp;B</b>]"


def test_header_shows_primary_and_menu_only_when_filled(client):
    head = make_user("leitung@example.org", Role.DEPARTMENT_HEAD)
    client.login(username=head.email, password=PASSWORD)
    listing = client.get(reverse("role_list")).content.decode()
    assert 'class="action-bar"' in listing  # „Rolle anlegen“
    assert "Weitere Aktionen" not in listing
    role = ParticipantRole.objects.filter(is_default=False).first()
    page = client.get(reverse("role_edit", args=[role.pk])).content.decode()
    assert "Weitere Aktionen" in page
    assert f'action="{reverse("role_delete", args=[role.pk])}"' in page
    assert page.count("<h1") == 1


def test_event_list_puts_subpages_in_menu(client):
    head = make_user("leitung@example.org", Role.DEPARTMENT_HEAD, Role.ADMIN)
    client.login(username=head.email, password=PASSWORD)
    events = client.get(reverse("event_list")).content.decode()
    assert "Weitere Aktionen" in events and reverse("role_list") in events
