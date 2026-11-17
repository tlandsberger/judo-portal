"""Hilfe: Kapitel je Rolle, öffentliche Kapitel, Links und Screenshots (ADR 0016)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from django.urls import reverse

from portal.accounts.models import Role
from portal.events.tests.conftest import make_trainer, make_user
from portal.help import chapters

pytestmark = pytest.mark.django_db
HELP_DIR = Path(chapters.__file__).parent


def slugs(user) -> list[str]:
    return [chapter.slug for chapter in chapters.visible(user)]


def test_chapters_by_role(parent, child, head):
    assert "termine" in slugs(parent)
    assert not {"team", "stunden", "mitglieder", "veranstaltungen", "abrechnungen", "benutzer"} & set(slugs(parent))
    trainer = make_trainer()
    assert {"team", "stunden"} <= set(slugs(trainer)) and "mitglieder" not in slugs(trainer)
    assert {"mitglieder", "veranstaltungen", "abrechnungen"} <= set(slugs(head))


def test_public_chapters_without_login(client):
    assert client.get(reverse("help_chapter", args=["erste-schritte"])).status_code == 200
    assert client.get(reverse("help_chapter", args=["fragen"])).status_code == 200
    assert client.get(reverse("help_chapter", args=["termine"])).status_code == 404
    assert "Hilfe zur Anmeldung" in client.get(reverse("account_login")).content.decode()


def test_foreign_chapter_is_404(client, parent):
    client.force_login(parent)
    assert client.get(reverse("help_chapter", args=["abrechnungen"])).status_code == 404


def test_every_chapter_renders_for_admin(client):
    admin = make_user("admin@example.org", Role.ADMIN, Role.TRAINER)
    client.force_login(admin)
    page = client.get(reverse("help_index")).content.decode()
    for chapter in chapters.CHAPTERS:
        if chapter.visible(admin):
            assert chapter.title in page
            assert client.get(reverse("help_chapter", args=[chapter.slug])).status_code == 200


def test_help_link_only_for_visible_chapter(client, parent, child):
    client.force_login(parent)
    assert 'aria-label="Hilfe: Termine und Anmeldung"' in client.get(reverse("agenda")).content.decode()


def test_screenshots_in_both_themes(client):
    page = client.get(reverse("help_chapter", args=["erste-schritte"])).content.decode()
    assert 'class="help-shot-light"' in page and "login-desktop.jpg" in page
    assert 'class="help-shot-dark"' in page and "login-desktop-dunkel.jpg" in page


def test_all_screenshots_exist():
    """Fehlt ein Bild, scheitert in Produktion das Rendern (Manifest der statischen Dateien)."""
    names = set()
    for template in (HELP_DIR / "templates" / "help" / "chapters").glob("*.html"):
        names.update(re.findall(r'\{% screenshot "([\w-]+)"', template.read_text()))
    assert names
    images = HELP_DIR / "static" / "help" / "img"
    missing = [
        f"{n}-{v}{t}.jpg"
        for n in sorted(names)
        for v in ("desktop", "handy")
        for t in ("", "-dunkel")
        if not (images / f"{n}-{v}{t}.jpg").exists()
    ]
    assert not missing, f"Screenshots fehlen, bitte `npm run help:screenshots`: {missing}"
