from datetime import timedelta

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from portal.accounts import services
from portal.accounts.adapter import PortalAccountAdapter
from portal.accounts.models import Invitation, Role, User
from portal.core.models import AuditEntry

pytestmark = pytest.mark.django_db


def make_user(email: str, *roles: Role, **extra: object) -> User:
    user = User.objects.create_user(email, password="Sicher-12345!", **extra)
    user.set_roles(list(roles))
    return user


class TestRoles:
    def test_admin_role_grants_technical_admin(self) -> None:
        user = make_user("ada@example.org", Role.ADMIN)
        assert user.is_staff and user.is_superuser
        user.set_roles([Role.MEMBER])
        assert not user.is_staff and not user.is_superuser

    def test_roles_are_normalised_and_inactive_users_have_none(self) -> None:
        user = make_user("tom@example.org", Role.TRAINER, Role.MEMBER)
        assert user.roles == ["member", "trainer"]
        assert user.role_labels == ["Mitglied", "Übungsleiter"]
        user.is_active = False
        assert not user.has_role(Role.TRAINER)


class TestInvitation:
    def test_invite_sends_mail_with_link(self, django_capture_on_commit_callbacks) -> None:
        with django_capture_on_commit_callbacks(execute=True):
            invitation = services.invite("Mia@Example.org", first_name="Mia", roles=["trainer", "unknown"])
        assert invitation.email == "mia@example.org"
        assert invitation.roles == ["trainer"]
        assert len(mail.outbox) == 1
        assert services.invitation_url(invitation) in mail.outbox[0].body
        assert "Hallo Mia" in mail.outbox[0].body

    def test_new_invitation_replaces_open_one(self, django_capture_on_commit_callbacks) -> None:
        with django_capture_on_commit_callbacks(execute=True):
            services.invite("mia@example.org")
            services.invite("mia@example.org")
        assert Invitation.objects.filter(email="mia@example.org").count() == 1

    def test_get_does_not_consume_invitation(self, client) -> None:
        invitation = services.invite("mia@example.org")
        response = client.get(reverse("accept_invitation", args=[invitation.token]))
        assert response.status_code == 200
        invitation.refresh_from_db()
        assert invitation.accepted_at is None

    def test_accept_creates_account_with_setup_session(self, client) -> None:
        invitation = services.invite("mia@example.org", first_name="Mia", last_name="Muster", roles=["trainer"])
        response = client.post(reverse("accept_invitation", args=[invitation.token]))
        assert response.status_code == 302 and response.url == reverse("setup_login")
        user = User.objects.get(email="mia@example.org")
        assert user.display_name == "Mia Muster"
        assert user.roles == ["trainer"]
        assert not user.has_usable_password()
        assert client.get(reverse("setup_login")).status_code == 200
        invitation.refresh_from_db()
        assert invitation.accepted_at is None  # erst mit Anmeldeweg eingelöst

    def test_expired_invitation_is_rejected(self, client) -> None:
        invitation = services.invite("mia@example.org")
        Invitation.objects.filter(pk=invitation.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
        assert client.get(reverse("accept_invitation", args=[invitation.token])).status_code == 410

    def test_adding_a_passkey_right_after_accepting_needs_no_reauthentication(self, client) -> None:
        invitation = services.invite("mia@example.org")
        client.post(reverse("accept_invitation", args=[invitation.token]))
        response = client.get(reverse("mfa_add_webauthn"))
        assert response.status_code == 200
        assert "Passkey anlegen" in response.content.decode()


class TestInitialAdmin:
    def test_invites_once_until_an_admin_exists(self, settings, django_capture_on_commit_callbacks) -> None:
        settings.INITIAL_ADMIN_EMAIL = "Chef@Example.org"
        with django_capture_on_commit_callbacks(execute=True):
            first = services.ensure_initial_admin()
            second = services.ensure_initial_admin()
        assert first is not None and first.roles == ["admin"]
        assert second is None
        assert len(mail.outbox) == 1
        make_user("chef@example.org", Role.ADMIN)
        Invitation.objects.all().delete()
        assert services.ensure_initial_admin() is None

    def test_does_nothing_without_setting(self, settings) -> None:
        settings.INITIAL_ADMIN_EMAIL = None
        assert services.ensure_initial_admin() is None


class TestAccountManagement:
    def test_members_and_trainers_may_not_manage_accounts(self, client) -> None:
        client.force_login(make_user("tom@example.org", Role.MEMBER, Role.TRAINER))
        assert client.get(reverse("user_list")).status_code == 403
        assert client.get(reverse("invite")).status_code == 403

    def test_anonymous_users_are_sent_to_login(self, client) -> None:
        response = client.get(reverse("user_list"))
        assert response.status_code == 302 and reverse("account_login") in response.url

    def test_department_head_invites_without_admin_role(self, client, django_capture_on_commit_callbacks) -> None:
        client.force_login(make_user("alex@example.org", Role.DEPARTMENT_HEAD))
        page = client.get(reverse("invite")).content.decode()
        assert "Administrator" not in page
        # Die Admin-Rolle ist für Abteilungsleiter keine gültige Auswahl.
        rejected = client.post(reverse("invite"), {"email": "mia@example.org", "roles": ["trainer", "admin"]})
        assert rejected.status_code == 200 and not Invitation.objects.exists()
        with django_capture_on_commit_callbacks(execute=True):
            response = client.post(reverse("invite"), {"email": "mia@example.org", "roles": ["trainer"]}, follow=True)
        assert "Einladung an mia@example.org verschickt." in response.content.decode()
        assert Invitation.objects.get().roles == ["trainer"]

    def test_existing_active_account_cannot_be_invited(self, client) -> None:
        client.force_login(make_user("alex@example.org", Role.DEPARTMENT_HEAD))
        make_user("mia@example.org")
        response = client.post(reverse("invite"), {"email": "mia@example.org"})
        assert "bereits einen aktiven Benutzer" in response.content.decode()

    def test_department_head_cannot_change_admins(self, client) -> None:
        client.force_login(make_user("alex@example.org", Role.DEPARTMENT_HEAD))
        admin = make_user("ada@example.org", Role.ADMIN)
        client.post(reverse("edit_user", args=[admin.pk]), {"roles": []})
        client.post(reverse("toggle_active", args=[admin.pk]))
        admin.refresh_from_db()
        assert admin.roles == ["admin"] and admin.is_active

    def test_admin_cannot_remove_own_admin_role_or_deactivate_self(self, client) -> None:
        admin = make_user("ada@example.org", Role.ADMIN)
        client.force_login(admin)
        client.post(reverse("edit_user", args=[admin.pk]), {"roles": ["member"]})
        client.post(reverse("toggle_active", args=[admin.pk]))
        admin.refresh_from_db()
        assert admin.has_role(Role.ADMIN) and admin.is_active

    def test_deactivated_account_is_logged_out(self, client) -> None:
        user = make_user("mia@example.org", Role.MEMBER)
        client.force_login(user)
        User.objects.filter(pk=user.pk).update(is_active=False)
        assert client.get(reverse("home")).status_code == 302

    def test_resend_renews_link(self, client) -> None:
        client.force_login(make_user("alex@example.org", Role.DEPARTMENT_HEAD))
        invitation = services.invite("mia@example.org")
        old_token = invitation.token
        client.post(reverse("resend_invitation", args=[invitation.pk]))
        invitation.refresh_from_db()
        assert invitation.token != old_token
        assert len(mail.outbox) == 1

    def test_user_actions_live_on_the_user_page(self, client) -> None:
        """Liste: Name öffnet den Benutzer; Einladung erneut senden und Deaktivieren stehen dort (ADR 0017)."""
        client.force_login(make_user("alex@example.org", Role.DEPARTMENT_HEAD))
        mia = make_user("mia@example.org", Role.TRAINER)
        mia.set_unusable_password()
        mia.save()
        listing = client.get(reverse("user_list")).content.decode()
        assert f'href="{reverse("edit_user", args=[mia.pk])}"' in listing
        assert reverse("toggle_active", args=[mia.pk]) not in listing
        assert reverse("reinvite_user", args=[mia.pk]) not in listing
        page = client.get(reverse("edit_user", args=[mia.pk])).content.decode()
        assert "noch nicht eingerichtet" in page
        assert reverse("reinvite_user", args=[mia.pk]) in page
        assert "Benutzer deaktivieren" in page
        response = client.post(reverse("toggle_active", args=[mia.pk]))
        assert response.url == reverse("edit_user", args=[mia.pk])
        mia.refresh_from_db()
        assert not mia.is_active


class TestLogin:
    def test_signup_is_closed(self, client) -> None:
        response = client.get(reverse("account_signup"))
        assert "Registrierung geschlossen" in response.content.decode() or response.status_code in (302, 403)

    def test_passkey_is_not_forced_as_second_factor(self) -> None:
        stages = PortalAccountAdapter().get_login_stages()
        assert not any(stage.startswith("allauth.mfa.stages.") for stage in stages)

    def test_login_page_offers_all_methods(self, client) -> None:
        page = client.get(reverse("account_login")).content.decode()
        assert "Mit Passkey anmelden" in page
        assert "Anmeldecode per E-Mail" in page
        assert "Mit Passwort anmelden" in page

    def test_password_login(self, client) -> None:
        make_user("mia@example.org", Role.MEMBER)
        response = client.post(
            reverse("account_login"), {"login": "mia@example.org", "password": "Sicher-12345!"}, follow=True
        )
        assert response.wsgi_request.user.is_authenticated

    def test_sliding_session_is_extended(self, client, settings) -> None:
        client.force_login(make_user("mia@example.org"))
        session = client.session
        session.set_expiry(settings.SESSION_COOKIE_AGE - 3 * 24 * 3600)
        session.save()
        client.get(reverse("home"))
        assert client.session.get_expiry_age() > settings.SESSION_COOKIE_AGE - 60


def test_security_page_offers_add_or_manage_passkey(client) -> None:
    """Ohne Passkey: „Hinzufügen“; mit Passkey nur „Verwalten“."""
    from allauth.mfa.models import Authenticator

    user = make_user("mia@example.org", Role.MEMBER)
    client.force_login(user)
    page = client.get(reverse("security")).content.decode()
    assert ">Hinzufügen<" in page and ">Verwalten<" not in page
    Authenticator.objects.create(user=user, type=Authenticator.Type.WEBAUTHN, data={"name": "Handy"})
    page = client.get(reverse("security")).content.decode()
    assert ">Verwalten<" in page and ">Hinzufügen<" not in page


class TestName:
    def test_users_change_their_own_name(self, client) -> None:
        user = make_user("mia@example.org", Role.MEMBER)
        client.force_login(user)
        response = client.post(
            reverse("security"), {"first_name": " Mia ", "last_name": "Muster", "phone": "0170 1"}, follow=True
        )
        assert "Deine Daten sind gespeichert." in response.content.decode()
        user.refresh_from_db()
        assert (user.first_name, user.last_name, user.phone) == ("Mia", "Muster", "0170 1")
        entry = AuditEntry.objects.get(action="profile")
        assert entry.changes["Vorname"] == ["", "Mia"] and "Telefon" in entry.changes

    def test_user_management_changes_name_and_roles(self, client) -> None:
        client.force_login(make_user("alex@example.org", Role.DEPARTMENT_HEAD))
        mia = make_user("mia@example.org", Role.MEMBER)
        page = client.get(reverse("edit_user", args=[mia.pk])).content.decode()
        assert 'name="first_name"' in page and 'name="last_name"' in page
        client.post(
            reverse("edit_user", args=[mia.pk]), {"first_name": "Mia", "last_name": "Muster", "roles": ["trainer"]}
        )
        mia.refresh_from_db()
        assert (mia.first_name, mia.last_name, mia.roles) == ("Mia", "Muster", ["trainer"])
        assert AuditEntry.objects.get(action="name").changes == {"Vorname": ["", "Mia"], "Nachname": ["", "Muster"]}
