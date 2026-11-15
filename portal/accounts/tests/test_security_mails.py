"""Sicherheitsmails gehen immer per Mail: Passwort, Passkey, Anmeldung auf neuem Gerät (ADR 0011)."""

from __future__ import annotations

import pytest
from allauth.account.adapter import get_adapter
from allauth.core import context
from django.core import mail
from django.test import Client, RequestFactory
from django.urls import reverse

from portal.accounts import devices, services
from portal.accounts.models import KnownDevice, User

pytestmark = pytest.mark.django_db

PASSWORD = "Sicher-12345!"
CHROME = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36"
IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 "
    "Version/18.1 Mobile/15E148 Safari/604.1"
)


@pytest.fixture
def user() -> User:
    return User.objects.create_user("mia@example.org", password=PASSWORD, first_name="Mia")


def login(user_agent: str) -> Client:
    client = Client(HTTP_USER_AGENT=user_agent)
    response = client.post(reverse("account_login"), {"login": "mia@example.org", "password": PASSWORD})
    assert response.status_code == 302
    return client


def test_describe_devices():
    assert devices.describe(CHROME) == "Chrome auf Windows"
    assert devices.describe(IPHONE) == "Safari auf iPhone"
    assert devices.fingerprint(CHROME) == devices.fingerprint(CHROME.replace("130.0.0.0", "131.0.1.2"))


def test_new_device_mail_not_on_first_login_and_not_twice(user):
    login(CHROME)
    assert mail.outbox == []
    login(CHROME.replace("130.0.0.0", "131.0.0.0"))  # Update desselben Browsers
    assert mail.outbox == []
    login(IPHONE)
    assert [m.subject for m in mail.outbox] == ["[Wedeler TSV Judo] Anmeldung auf einem neuen Gerät"]
    assert "Safari auf iPhone" in mail.outbox[0].body
    login(IPHONE)
    assert len(mail.outbox) == 1
    assert KnownDevice.objects.filter(user=user).count() == 2


def test_password_change_mail(user):
    client = login(CHROME)
    client.post(
        reverse("account_change_password"),
        {"oldpassword": PASSWORD, "password1": "Neu-Sicher-678!", "password2": "Neu-Sicher-678!"},
    )
    assert [m.subject for m in mail.outbox] == ["[Wedeler TSV Judo] Dein Passwort wurde geändert"]
    assert "Dein Passwort wurde geändert." in mail.outbox[0].body
    assert "melde dich bitte umgehend" in mail.outbox[0].body


def test_passkey_mail_text(user):
    request = RequestFactory().get("/")
    request.session = {}  # type: ignore[assignment]
    with context.request_context(request):
        get_adapter().send_notification_mail("mfa/email/webauthn_added", user)
    assert mail.outbox[0].subject == "[Wedeler TSV Judo] Neuer Passkey für deinen Zugang"


def test_no_security_mail_during_invitation_setup():
    invitation = services.invite("neu@example.org", send=False)
    client = Client()
    client.post(reverse("accept_invitation", args=[invitation.token]))
    client.post(reverse("account_set_password"), {"password1": PASSWORD, "password2": PASSWORD})
    assert mail.outbox == []
