"""Alle Mails gehen als HTML (Vereins-Look aus ``email/base.html``) mit Textfassung als Alternative."""

from __future__ import annotations

from pathlib import Path

import pytest
from django.conf import settings
from django.core import mail
from django.template.loader import render_to_string
from django.urls import reverse

from portal.accounts.models import User

pytestmark = pytest.mark.django_db

ROOT = Path(settings.BASE_DIR) / "portal"


def text_templates() -> list[Path]:
    """Alle Textfassungen von Mails im Portal (allauth-Vorlagen und eigene)."""
    found = [*ROOT.glob("templates/account/email/*_message.txt"), *ROOT.glob("templates/mfa/email/*_message.txt")]
    found += [p for p in ROOT.glob("**/templates/**/email/*.txt") if not p.name.endswith("_subject.txt")]
    return sorted({p for p in found if p.name != "base_message.txt"})


@pytest.mark.parametrize("path", text_templates(), ids=lambda p: str(p.relative_to(ROOT)))
def test_every_text_mail_has_an_html_version(path: Path) -> None:
    assert path.with_suffix(".html").exists(), f"HTML-Fassung fehlt zu {path.name}"


def test_html_versions_use_the_shared_layout() -> None:
    for path in text_templates():
        html = render_to_string(
            str(path.with_suffix(".html")).split("/templates/", 1)[1],
            {"code": "ABCD-1234", "url": "https://example.org/x", "user": User(first_name="Mia")},
        )
        assert "Wedeler TSV Judo" in html and "judo@wedeler-tsv.de" in html, path.name


def test_login_code_mail_goes_out_as_html(client) -> None:
    User.objects.create_user("mia@example.org", password="Sicher-12345!")
    client.post(reverse("account_request_login_code"), {"email": "mia@example.org"})
    [message] = mail.outbox
    html, mime = message.alternatives[0]
    assert mime == "text/html" and "Anmeldecode" in html
