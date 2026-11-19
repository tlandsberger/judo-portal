"""Fachliche Abläufe rund um Benutzer: einladen, Einladung annehmen, ersten Administrator anlegen."""

from __future__ import annotations

import logging

from allauth.account.internal.flows.login import record_authentication
from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth import login
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.http import HttpRequest
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from portal.core import audit

from . import devices
from .models import EMAIL_CHANGE_DAYS, EmailChange, Invitation, KnownDevice, Role, User
from .signals import email_changed, greeting_requested, invitation_accepted, own_member_requested

log = logging.getLogger(__name__)

AUTH_BACKEND = "allauth.account.auth_backends.AuthenticationBackend"


def invitation_url(invitation: Invitation) -> str:
    return settings.BASE_URL + reverse("accept_invitation", args=[invitation.token])


def greeting(*, user: User | None = None, invitation: Invitation | None = None) -> str:
    """Anrede ohne Satzzeichen: „Hallo Anna“; ohne Vornamen fragen wir andere Apps (z. B. „Liebe Eltern von Mia“)."""
    first_name = user.first_name if user is not None else invitation.first_name if invitation is not None else ""
    if first_name:
        return f"Hallo {first_name}"
    for _receiver, answer in greeting_requested.send(sender=User, user=user, invitation=invitation):
        if answer:
            return str(answer)
    return "Hallo"


def send_invitation(invitation: Invitation) -> None:
    context = {
        "greeting": greeting(invitation=invitation),
        "invitation": invitation,
        "url": invitation_url(invitation),
        "days": settings.INVITATION_DAYS,
        "base_url": settings.BASE_URL,
    }
    subject = settings.EMAIL_SUBJECT_PREFIX + "Einladung ins Vereinsportal"
    message = EmailMultiAlternatives(
        subject=subject,
        body=render_to_string("accounts/email/invitation.txt", context),
        to=[invitation.email],
    )
    message.attach_alternative(render_to_string("accounts/email/invitation.html", context), "text/html")
    message.send()


@transaction.atomic
def invite(
    email: str,
    *,
    first_name: str = "",
    last_name: str = "",
    roles: list[str] | None = None,
    invited_by: User | None = None,
    send: bool = True,
) -> Invitation:
    """Lädt eine Person ein. Offene Einladungen an dieselbe Adresse werden ersetzt.

    Mit ``send=False`` wird keine Mail verschickt; der Link (``invitation_url``) wird dann z. B. per Messenger
    weitergegeben.
    """
    email = email.strip().lower()
    Invitation.objects.filter(email=email, accepted_at__isnull=True).delete()
    invitation = Invitation.objects.create(
        email=email,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        roles=[r for r in Role.values if r in set(roles or [])],
        invited_by=invited_by,
        user=User.objects.filter(email=email).first(),
    )
    if send:
        transaction.on_commit(lambda: send_invitation(invitation))
    role_text = ", ".join(Role(r).label for r in invitation.roles)
    audit.log(
        invited_by,
        audit.Area.USERS,
        "invite",
        f"Einladung an {email}{f' ({role_text})' if role_text else ''}{'' if send else ', nur Link'}",
        user=invitation.user,
    )
    log.info("Einladung für %s erstellt (%s)", email, "per Mail" if send else "nur Link")
    return invitation


def resend(invitation: Invitation, by: User | None = None) -> None:
    invitation.renew()
    send_invitation(invitation)
    audit.log(by, audit.Area.USERS, "invite_resend", f"Einladung an {invitation.email} erneut verschickt")


def new_link(invitation: Invitation, by: User | None = None) -> str:
    """Erzeugt einen neuen Link (der alte wird ungültig), ohne Mail-Versand."""
    invitation.renew()
    audit.log(by, audit.Area.USERS, "invite_link", f"Neuer Einladungslink für {invitation.email}")
    log.info("Neuer Einladungslink für %s erzeugt (ohne Mail)", invitation.email)
    return invitation_url(invitation)


def reinvite(user: User, *, invited_by: User | None = None, send: bool = True) -> Invitation:
    """Neue Einladung für einen Benutzer, der seinen Zugang noch nicht eingerichtet hat."""
    return invite(user.email, first_name=user.first_name, last_name=user.last_name, invited_by=invited_by, send=send)


# Sitzungsschlüssel der Einrichtungs-Sitzung nach einem Klick auf den Einladungslink
SETUP_SESSION_KEY = "portal_invitation_setup"
SETUP_MINUTES = 30


def has_login_method(user: User) -> bool:
    """Hat der Benutzer einen eigenen Anmeldeweg (Passwort oder Passkey)? Der Mail-Code zählt nicht."""
    from allauth.mfa.models import Authenticator

    return (
        user.has_usable_password() or Authenticator.objects.filter(user=user, type=Authenticator.Type.WEBAUTHN).exists()
    )


def is_set_up(user: User) -> bool:
    """Zugang eingerichtet: eigener Anmeldeweg oder schon regulär (z. B. per Code) angemeldet."""
    if has_login_method(user):
        return True
    return user.last_login is not None and not user.invitations.filter(accepted_at__isnull=True).exists()


@transaction.atomic
def accept(invitation: Invitation, request: HttpRequest) -> User | None:
    """Klick auf „Einladung annehmen“.

    Der Klick allein gibt nie vollen Zugang – auch Mail-Scanner klicken Links und Buttons an. Er legt den Benutzer an
    und öffnet eine kurze Einrichtungs-Sitzung, in der nur Passkey oder Passwort eingerichtet werden können
    (``SetupSessionMiddleware``). Eingelöst ist die Einladung erst, wenn ein Anmeldeweg existiert.

    Hat der Benutzer schon einen Anmeldeweg (z. B. erneute Einladung eines deaktivierten Benutzers), wird er nur
    reaktiviert und nicht angemeldet; Rückgabe ``None``.
    """
    invitation = Invitation.objects.select_for_update().get(pk=invitation.pk)
    user = invitation.user or User.objects.filter(email=invitation.email).first()
    if user is None:
        user = User.objects.create_user(
            invitation.email, first_name=invitation.first_name, last_name=invitation.last_name
        )
    else:
        user.first_name = user.first_name or invitation.first_name
        user.last_name = user.last_name or invitation.last_name
        user.is_active = True
        user.save(update_fields=["first_name", "last_name", "is_active"])
    user.set_roles(sorted(set(user.roles) | set(invitation.roles)))
    EmailAddress.objects.update_or_create(user=user, email=user.email, defaults={"verified": True, "primary": True})
    invitation.user = user
    invitation.save(update_fields=["user"])
    audit.log(user, audit.Area.USERS, "invite_accept", f"Einladung angenommen ({user.email})", user=user)
    invitation_accepted.send(sender=Invitation, invitation=invitation, user=user)

    if has_login_method(user):
        complete_invitations(user)
        log.info("Einladung für %s angenommen, Benutzer hatte bereits einen Anmeldeweg", user.email)
        return None

    login(request, user, backend=AUTH_BACKEND)
    # Ohne „Angemeldet bleiben“: Die Einrichtungs-Sitzung endet mit dem Browser und nach SETUP_MINUTES.
    request.session.set_expiry(0)
    request.session[SETUP_SESSION_KEY] = {"invitation": invitation.pk, "started": timezone.now().timestamp()}
    # Der Link belegt den Besitz der Mail-Adresse; so kann direkt ein Passkey angelegt werden.
    record_authentication(request, user, method="code", email=user.email, reauthenticated=True)
    log.info(
        "Einladung für %s geöffnet (Einrichtung offen), Browser: %s",
        user.email,
        request.headers.get("User-Agent", "-")[:200],
    )
    return user


def mark_setup_completed(request: HttpRequest | None) -> None:
    """Merkt in der laufenden Einrichtungs-Sitzung, dass hier ein Anmeldeweg angelegt wurde."""
    session = getattr(request, "session", None)
    if session is not None and session.get(SETUP_SESSION_KEY):
        session[SETUP_SESSION_KEY] = {**session[SETUP_SESSION_KEY], "completed": True}


def invitation_state(invitation: Invitation | None) -> str:
    """Zustand für die Einladungsseite: open, done, expired oder unknown."""
    if invitation is None:
        return "unknown"
    if invitation.accepted_at is not None:
        return "done"
    if invitation.expires_at <= timezone.now():
        return "expired"
    return "open"


def check_new_device(request: HttpRequest, user: User) -> None:
    """Bei der Anmeldung: Ist der Browser neu, bekommt der Benutzer eine Warnung per Mail (ADR 0011).

    Die erste Anmeldung überhaupt (z. B. nach der Einladung) zählt nicht; da lernt das Portal das Gerät nur kennen.
    """
    from allauth.account.adapter import get_adapter

    user_agent = request.headers.get("User-Agent", "")
    had_devices = KnownDevice.objects.filter(user=user).exists()
    device, created = KnownDevice.objects.get_or_create(
        user=user, fingerprint=devices.fingerprint(user_agent), defaults={"description": devices.describe(user_agent)}
    )
    if not created:
        KnownDevice.objects.filter(pk=device.pk).update(last_seen=timezone.now())
        return
    if had_devices:
        log.info("Anmeldung von %s auf neuem Gerät (%s)", user.email, device.description)
        audit.log(user, audit.Area.LOGIN, "new_device", f"Anmeldung von neuem Gerät: {device.description}", user=user)
        get_adapter(request).send_notification_mail("account/email/new_device", user, {"device": device.description})


def complete_invitations(user: User) -> None:
    """Offene Einladungen eines Benutzers gelten als eingelöst (Anmeldeweg eingerichtet oder regulär angemeldet)."""
    count = Invitation.objects.filter(user=user, accepted_at__isnull=True).update(accepted_at=timezone.now())
    if count:
        log.info("Einladung für %s eingelöst", user.email)


def ensure_initial_admin() -> Invitation | None:
    """Lädt PORTAL_INITIAL_ADMIN_EMAIL als Administrator ein, solange es keinen aktiven Administrator gibt."""
    email = (settings.INITIAL_ADMIN_EMAIL or "").strip().lower()
    if not email:
        return None
    admins = [u for u in User.objects.filter(is_active=True) if u.has_role(Role.ADMIN)]
    # Ein Administrator zählt erst, wenn er seinen Zugang eingerichtet hat (nicht nur ein Scanner-Klick).
    if any(has_login_method(u) or not u.invitations.filter(accepted_at__isnull=True).exists() for u in admins):
        return None
    open_invitation = Invitation.objects.filter(email=email, accepted_at__isnull=True).first()
    if open_invitation and open_invitation.is_valid:
        return None
    invitation = invite(email, roles=[Role.ADMIN])
    log.warning("Erster Administrator eingeladen: %s – Link: %s", email, invitation_url(invitation))
    return invitation


# E-Mail-Adresse ändern (ADR 0011): wirksam erst mit dem Link an die neue Adresse, die alte bekommt einen Hinweis.


class EmailChangeError(Exception):
    pass


def own_member_name(user: User) -> str:
    """Name des eigenen Mitgliedsprofils (von ``portal.members`` über ein Signal), sonst ""."""
    for _receiver, answer in own_member_requested.send(sender=User, user=user):
        if answer:
            return str(answer)
    return ""


def email_change_url(change: EmailChange) -> str:
    return settings.BASE_URL + reverse("confirm_email_change", args=[change.token])


def pending_email_change(user: User) -> EmailChange | None:
    change = EmailChange.objects.filter(user=user).first()
    return change if change is not None and change.is_valid else None


def _check_email_free(email: str, user: User) -> None:
    if User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
        raise EmailChangeError("Diese E-Mail-Adresse gehört schon zu einem anderen Benutzer.")
    if EmailAddress.objects.filter(email__iexact=email).exclude(user=user).exists():
        raise EmailChangeError("Diese E-Mail-Adresse gehört schon zu einem anderen Benutzer.")


@transaction.atomic
def request_email_change(user: User, email: str, by: User, *, sync_member: bool = False) -> EmailChange:
    """Neue Adresse vormerken und den Bestätigungslink an sie schicken. Eine ältere offene Änderung ersetzt sie."""
    email = email.strip()
    if email.lower() == user.email.lower():
        raise EmailChangeError("Das ist schon die aktuelle E-Mail-Adresse.")
    _check_email_free(email, user)
    EmailChange.objects.filter(user=user).delete()
    change = EmailChange.objects.create(
        user=user, email=email, sync_member=sync_member and bool(own_member_name(user)), requested_by=by
    )
    who = "selbst" if by.pk == user.pk else f"von {by.display_name}"
    audit.log(by, audit.Area.LOGIN, "email_change_requested", f"Neue E-Mail-Adresse angefragt ({who})", user=user)
    transaction.on_commit(lambda: send_email_change(change))
    return change


def send_email_change(change: EmailChange) -> None:
    context = {
        "greeting": greeting(user=change.user),
        "change": change,
        "url": email_change_url(change),
        "days": EMAIL_CHANGE_DAYS,
        "by_other": change.requested_by_id not in (None, change.user_id),
        "requested_by": change.requested_by,
    }
    message = EmailMultiAlternatives(
        subject=settings.EMAIL_SUBJECT_PREFIX + "Neue E-Mail-Adresse bestätigen",
        body=render_to_string("accounts/email/email_change.txt", context),
        to=[change.email],
    )
    message.attach_alternative(render_to_string("accounts/email/email_change.html", context), "text/html")
    message.send()


def cancel_email_change(user: User, by: User) -> None:
    if EmailChange.objects.filter(user=user).delete()[0]:
        audit.log(by, audit.Area.LOGIN, "email_change_cancelled", "Neue E-Mail-Adresse verworfen", user=user)


@transaction.atomic
def confirm_email_change(change: EmailChange, request: HttpRequest | None = None) -> User:
    """Link bestätigt: Die neue Adresse gilt (auch für die Anmeldung), die alte bekommt einen Sicherheitshinweis."""
    if not change.is_valid:
        raise EmailChangeError("Der Link ist abgelaufen. Ändere die E-Mail-Adresse bitte noch einmal.")
    user = change.user
    _check_email_free(change.email, user)
    old_email = user.email
    user.email = change.email
    user.save(update_fields=["email"])
    EmailAddress.objects.filter(user=user).delete()
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
    sync_member, by = change.sync_member, change.requested_by
    change.delete()
    audit.log(
        user,
        audit.Area.LOGIN,
        "email_changed",
        "E-Mail-Adresse geändert",
        user=user,
        changes={"E-Mail": [old_email, user.email]},
    )
    log.info("E-Mail-Adresse von Benutzer %s geändert", user.pk)
    email_changed.send(sender=User, user=user, old_email=old_email, sync_member=sync_member, by=by)
    transaction.on_commit(lambda: _notify_old_address(user, old_email, request))
    return user


def _notify_old_address(user: User, old_email: str, request: HttpRequest | None) -> None:
    """Sicherheitshinweis an die bisherige Adresse, wie die übrigen Sicherheitsmails von allauth (ADR 0011)."""
    from allauth.account.adapter import get_adapter
    from allauth.core import context

    with context.request_context(request):
        get_adapter(request).send_notification_mail(
            "account/email/email_changed", user, {"old_email": old_email, "new_email": user.email}, email=old_email
        )
