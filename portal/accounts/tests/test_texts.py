"""Eigene Übersetzungen (portal/locale): Du-Form, „Zugang“ statt „Konto“, „Passkey“ statt „Sicherheitsschlüssel“."""

import re
from pathlib import Path

import pytest
from babel.messages.catalog import Catalog
from babel.messages.mofile import read_mo
from babel.messages.pofile import read_po
from django.conf import settings
from django.urls import reverse
from django.utils import translation
from django.utils.translation import gettext, ngettext

LOCALE = Path(settings.BASE_DIR) / "portal" / "locale" / "de" / "LC_MESSAGES"
FORMAL = re.compile(r"\b(Sie|Ihr|Ihre|Ihren|Ihrem|Ihnen|Konto|Kontos|Konten)\b")


def test_mo_matches_po() -> None:
    """Die .mo ist nach der letzten Änderung der .po neu kompiliert (siehe Kopf der .po)."""
    with (LOCALE / "django.po").open("rb") as po, (LOCALE / "django.mo").open("rb") as mo:
        source, compiled = read_po(po), read_mo(mo)

    def entries(catalog: Catalog) -> dict[object, object]:
        return {_key(m.id): _key(m.string) for m in catalog if m.id}

    assert entries(source) == entries(compiled)


def _key(value: object) -> object:
    return tuple(value) if isinstance(value, (list, tuple)) else value


def test_translations_are_informal() -> None:
    with (LOCALE / "django.po").open("rb") as po:
        for message in read_po(po):
            strings = message.string if isinstance(message.string, tuple) else (message.string,)
            for text in strings:
                assert not FORMAL.search(text), text


def test_portal_translations_override_allauth() -> None:
    with translation.override("de"):
        assert gettext("Unknown Account") == "Unbekannter Zugang"
        assert gettext("Security key added.") == "Passkey hinzugefügt."
        assert ngettext("You have added %(count)s security key.", "You have added %(count)s security keys.", 2) == (
            "Du hast %(count)s Passkeys hinzugefügt."
        )


@pytest.mark.django_db
@pytest.mark.parametrize("url_name", ["account_reset_password", "account_request_login_code"])
def test_allauth_pages_are_informal(client, url_name: str) -> None:
    response = client.get(reverse(url_name))
    assert response.status_code == 200
    text = re.sub(r"<[^>]+>", " ", response.content.decode())
    assert not FORMAL.search(text), FORMAL.search(text)
