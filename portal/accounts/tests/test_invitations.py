"""Einladungen sind sicher gegen Mail-Scanner, die Links öffnen und Buttons klicken."""

import time
from datetime import timedelta

import pytest
from allauth.mfa.models import Authenticator
from django.core import mail
from django.core.management import call_command
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from portal.accounts import services
from portal.accounts.models import Invitation, Role, User

pytestmark = pytest.mark.django_db


def accept(client: Client, invitation: Invitation):
    return client.post(reverse("accept_invitation", args=[invitation.token]))


def set_password(client: Client) -> None:
    response = client.post(
        reverse("account_set_password"), {"password1": "Sicher-12345!", "password2": "Sicher-12345!"}
    )
    assert response.status_code == 302, response.content.decode()[:500]


def make_staff(email: str = "alex@example.org") -> User:
    user = User.objects.create_user(email, password="Sicher-12345!")
    user.set_roles([Role.DEPARTMENT_HEAD])
    return user


class TestSetupSession:
    def test_setup_session_only_reaches_setup_pages(self, client) -> None:
        invitation = services.invite("chef@example.org", roles=["admin"])
        accept(client, invitation)
        for name in ["home", "user_list", "invite", "security", "components"]:
            response = client.get(reverse(name))
            assert response.status_code == 302 and response.url == reverse("setup_login"), name
        assert client.get("/technik/").url == reverse("setup_login")
        assert client.get(reverse("setup_login")).status_code == 200
        assert client.get(reverse("account_set_password")).status_code == 200
        assert client.get(reverse("mfa_add_webauthn")).status_code == 200

    def test_setup_session_ends_with_browser_and_expires(self, client, monkeypatch) -> None:
        invitation = services.invite("mia@example.org")
        accept(client, invitation)
        assert client.session.get_expire_at_browser_close()
        later = time.time() + (services.SETUP_MINUTES + 1) * 60
        monkeypatch.setattr(
            "django.utils.timezone.now", lambda: timezone.datetime.fromtimestamp(later, tz=timezone.UTC)
        )
        response = client.get(reverse("setup_login"))
        assert response.status_code == 302 and response.url == reverse("account_login")

    def test_scanner_then_person(self) -> None:
        invitation = services.invite("chef@example.org", roles=["admin"])
        scanner, person = Client(), Client()
        accept(scanner, invitation)
        accept(scanner, invitation)  # Doppelklick des Scanners
        assert accept(person, invitation).url == reverse("setup_login")
        set_password(person)
        assert person.get(reverse("user_list")).status_code == 200  # volle Sitzung
        invitation.refresh_from_db()
        assert invitation.accepted_at is not None
        assert User.objects.filter(email="chef@example.org").count() == 1
        # Die Scanner-Sitzung wird abgemeldet, statt freigeschaltet zu werden.
        response = scanner.get(reverse("home"))
        assert response.status_code == 302 and response.url.startswith(reverse("account_login"))
        assert scanner.get(reverse("user_list")).url.startswith(reverse("account_login"))

    def test_passkey_completes_setup(self, client) -> None:
        invitation = services.invite("mia@example.org")
        accept(client, invitation)
        user = User.objects.get(email="mia@example.org")
        # Was der allauth-Ablauf „Passkey hinzufügen“ am Ende tut: Authenticator speichern und Signal senden.
        from allauth.mfa.signals import authenticator_added

        authenticator = Authenticator.objects.create(user=user, type=Authenticator.Type.WEBAUTHN, data={})
        request = type("R", (), {"session": client.session})()
        authenticator_added.send(sender=Authenticator, request=request, user=user, authenticator=authenticator)
        request.session.save()
        assert client.get(reverse("home")).status_code == 200

    def test_login_by_code_instead(self, client) -> None:
        invitation = services.invite("mia@example.org")
        accept(client, invitation)
        response = client.post(reverse("setup_login_by_code"))
        assert response.url == reverse("account_request_login_code")
        assert client.get(reverse("home")).status_code == 302  # abgemeldet, Zugang erst mit Code

    def test_regular_login_completes_open_invitation(self, client, django_capture_on_commit_callbacks) -> None:
        invitation = services.invite("mia@example.org")
        accept(Client(), invitation)
        user = User.objects.get(email="mia@example.org")
        user.set_password("Sicher-12345!")
        user.save()
        client.post(reverse("account_login"), {"login": "mia@example.org", "password": "Sicher-12345!"})
        invitation.refresh_from_db()
        assert invitation.accepted_at is not None

    def test_reinvited_account_with_login_method_is_not_logged_in(self, client) -> None:
        user = User.objects.create_user("mia@example.org", password="Sicher-12345!")
        user.is_active = False
        user.save()
        invitation = services.invite("mia@example.org", roles=["trainer"])
        response = accept(client, invitation)
        assert "Dein Zugang ist bereit" in response.content.decode()
        user.refresh_from_db()
        assert user.is_active and user.roles == ["trainer"]
        assert client.get(reverse("home")).status_code == 302


class TestInvitationPage:
    def test_states(self, client) -> None:
        assert "gibt es nicht" in client.get(reverse("accept_invitation", args=["unbekannt"])).content.decode()
        expired = services.invite("alt@example.org")
        Invitation.objects.filter(pk=expired.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
        assert "abgelaufen" in client.get(reverse("accept_invitation", args=[expired.token])).content.decode()
        done = services.invite("fertig@example.org")
        Invitation.objects.filter(pk=done.pk).update(accepted_at=timezone.now())
        assert "Zugang ist bereit" in client.get(reverse("accept_invitation", args=[done.token])).content.decode()

    def test_head_has_no_body_and_page_is_not_indexed(self, client) -> None:
        invitation = services.invite("mia@example.org")
        head = client.head(reverse("accept_invitation", args=[invitation.token]))
        assert head.status_code == 200 and head.content == b""
        page = client.get(reverse("accept_invitation", args=[invitation.token]))
        assert page["X-Robots-Tag"].startswith("noindex")
        assert "no-store" in page["Cache-Control"] or "no-cache" in page["Cache-Control"]


class TestLinkWithoutMail:
    def test_invite_link_only_sends_no_mail(self, client, django_capture_on_commit_callbacks) -> None:
        client.force_login(make_staff())
        with django_capture_on_commit_callbacks(execute=True):
            response = client.post(reverse("invite"), {"email": "mia@example.org", "action": "link"})
        invitation = Invitation.objects.get(email="mia@example.org")
        assert services.invitation_url(invitation) in response.content.decode()
        assert len(mail.outbox) == 0

    def test_copy_link_renews_token(self, client) -> None:
        client.force_login(make_staff())
        invitation = services.invite("mia@example.org", send=False)
        old = invitation.token
        response = client.post(reverse("invitation_link", args=[invitation.pk]))
        invitation.refresh_from_db()
        assert invitation.token != old
        assert services.invitation_url(invitation) in response.content.decode()
        assert response["Cache-Control"] == "no-store"
        assert len(mail.outbox) == 0

    def test_only_staff_may_create_links(self, client) -> None:
        member = User.objects.create_user("tom@example.org")
        member.set_roles([Role.TRAINER])
        client.force_login(member)
        invitation = services.invite("mia@example.org", send=False)
        assert client.post(reverse("invitation_link", args=[invitation.pk])).status_code == 403

    def test_reinvite_user_not_set_up(self, client, django_capture_on_commit_callbacks) -> None:
        client.force_login(make_staff())
        accept(Client(), services.invite("mia@example.org"))
        account = User.objects.get(email="mia@example.org")
        assert not services.is_set_up(account)
        page = client.get(reverse("user_list")).content.decode()
        assert "noch nicht eingerichtet" in page
        with django_capture_on_commit_callbacks(execute=True):
            client.post(reverse("reinvite_user", args=[account.pk]), {"action": "send"})
        assert len(mail.outbox) == 1
        response = client.post(reverse("reinvite_user", args=[account.pk]), {"action": "link"})
        assert "/einladung/" in response.content.decode()


class TestRecovery:
    def test_invite_command_prints_link(self, capsys, django_capture_on_commit_callbacks) -> None:
        with django_capture_on_commit_callbacks(execute=True):
            call_command("invite", "Chef@Example.org", "--admin", "--no-mail")
        invitation = Invitation.objects.get(email="chef@example.org")
        assert invitation.roles == ["admin"]
        assert services.invitation_url(invitation) in capsys.readouterr().out
        assert len(mail.outbox) == 0

    def test_initial_admin_reinvited_after_scanner_click(self, settings, django_capture_on_commit_callbacks) -> None:
        settings.INITIAL_ADMIN_EMAIL = "chef@example.org"
        with django_capture_on_commit_callbacks(execute=True):
            invitation = services.ensure_initial_admin()
        assert invitation is not None
        accept(Client(), invitation)  # Scanner: Benutzer entsteht, aber nicht eingerichtet
        Invitation.objects.filter(pk=invitation.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
        with django_capture_on_commit_callbacks(execute=True):
            again = services.ensure_initial_admin()
        assert again is not None and again.pk != invitation.pk


class TestPasswordRedirect:
    def test_after_setting_password_in_setup_back_to_overview(self, client) -> None:
        accept(client, services.invite("mia@example.org"))
        response = client.post(
            reverse("account_set_password"), {"password1": "Sicher-12345!", "password2": "Sicher-12345!"}
        )
        assert response.url == reverse("setup_login")

    def test_after_changing_password_back_to_security(self, client) -> None:
        client.force_login(make_staff())
        response = client.post(
            reverse("account_change_password"),
            {"oldpassword": "Sicher-12345!", "password1": "Neu-Sicher-678!", "password2": "Neu-Sicher-678!"},
        )
        assert response.url == reverse("security")
