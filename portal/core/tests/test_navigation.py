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
    titles = set(re.findall(r"menu-title[^>]*>(\w+)<", sidebar))
    assert "Verwaltung" in titles
    assert "Training" not in titles
    for url in (reverse("billing_index"), reverse("claim_list"), reverse("event_list")):
        assert tiles[url] == side[url]


def test_old_hours_urls_redirect_to_billing(client):
    """Altlast: Weiterleitungen von „Meine Stunden“ für ältere Links (beim nächsten Aufräumen entfernen)."""
    for path in ("/stunden/", "/einsaetze/"):
        response = client.get(path)
        assert response.status_code == 301
        assert response.url == reverse("billing_index")


def test_parent_sees_no_groups(client):
    parent = make_user("eltern@example.org")
    client.login(username=parent.email, password=PASSWORD)
    html = client.get(reverse("home")).content.decode()
    assert "menu-title" not in html
    assert reverse("claim_list") not in html
