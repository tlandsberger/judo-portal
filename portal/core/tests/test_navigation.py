"""Seitenleiste und Kacheln der Startseite zeigen dieselben Punkte mit denselben Icons."""

from __future__ import annotations

import re

import pytest
from django.urls import reverse

from portal.accounts.models import Role
from portal.events.tests.conftest import PASSWORD, make_trainer, make_user

pytestmark = pytest.mark.django_db


def links(html: str, part: str) -> dict[str, str]:
    """Ziel-URL → Icon in einem Teil der Seite (Seitenleiste bzw. Hauptinhalt)."""
    return dict(re.findall(r'<a href="([^"]+)"[^>]*><i class="bi (bi-[\w-]+)"', part)) | {
        url: icon
        for url, icon in re.findall(
            r'href="([^"]+)">\s*<div class="card-body[^>]*>\s*<span[^>]*><i class="bi (bi-[\w-]+)', part
        )
    }


def test_tiles_match_sidebar(client):
    user = make_trainer()
    user.set_roles([Role.TRAINER, Role.DEPARTMENT_HEAD])
    user.save()
    client.login(username=user.email, password=PASSWORD)
    html = client.get(reverse("home")).content.decode()
    main, rest = html.split("<aside", 1)
    sidebar = rest.split("</aside>", 1)[0]
    side, tiles = links(html, sidebar), links(html, main)
    assert {"Training", "Verwaltung"} <= set(re.findall(r"menu-title[^>]*>(\w+)<", sidebar))
    for url in (reverse("my_hours"), reverse("billing_index"), reverse("claim_list"), reverse("event_list")):
        assert tiles[url] == side[url]


def test_parent_sees_no_groups(client):
    parent = make_user("eltern@example.org")
    client.login(username=parent.email, password=PASSWORD)
    html = client.get(reverse("home")).content.decode()
    assert "menu-title" not in html
    assert reverse("claim_list") not in html
