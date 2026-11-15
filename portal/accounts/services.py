"""Fachliche Abläufe rund um Konten: einladen, Einladung annehmen, ersten Administrator anlegen."""

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

from .models import Invitation, Role, User

log = logging.getLogger(__name__)

AUTH_BACKEND = "allauth.account.auth_backends.AuthenticationBackend"


def invitation_url(invitation: Invitation) -> str:
    return settings.BASE_URL + reverse("accept_invitation", args=[invitation.token])


def send_invitation(invitation: Invitation) -> None:
    context = {
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
    log.info("Einladung für %s erstellt (%s)", email, "per Mail" if send else "nur Link")
    return invitation


def resend(invitation: Invitation) -> None:
    invitation.renew()
    send_invitation(invitation)


def new_link(invitation: Invitation) -> str:
    """Erzeugt einen neuen Link (der alte wird ungültig), ohne Mail-Versand."""
    invitation.renew()
    log.info("Neuer Einladungslink für %s erzeugt (ohne Mail)", invitation.email)
    return invitation_url(invitation)


def reinvite(user: User, *, invited_by: User | None = None, send: bool = True) -> Invitation:
    """Neue Einladung für ein Konto, das seinen Zugang noch nicht eingerichtet hat."""
    return invite(user.email, first_name=user.first_name, last_name=user.last_name, invited_by=invited_by, send=send)


# Sitzungsschlüssel der Einrichtungs-Sitzung nach einem Klick auf den Einladungslink
SETUP_SESSION_KEY = "portal_invitation_setup"
SETUP_MINUTES = 30


def has_login_method(user: User) -> bool:
    """Hat das Konto einen eigenen Anmeldeweg (Passwort oder Passkey)? Der Mail-Code zählt nicht – er ist immer da."""
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

    Der Klick allein gibt nie vollen Zugang – auch Mail-Scanner klicken Links und Buttons an. Er legt das Konto an
    und öffnet eine kurze Einrichtungs-Sitzung, in der nur Passkey oder Passwort eingerichtet werden können
    (``SetupSessionMiddleware``). Eingelöst ist die Einladung erst, wenn ein Anmeldeweg existiert.

    Hat das Konto schon einen Anmeldeweg (z. B. erneute Einladung eines deaktivierten Kontos), wird es nur
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

    if has_login_method(user):
        complete_invitations(user)
        log.info("Einladung für %s angenommen, Konto hatte bereits einen Anmeldeweg", user.email)
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


def complete_invitations(user: User) -> None:
    """Offene Einladungen eines Kontos gelten als eingelöst (Anmeldeweg eingerichtet oder regulär angemeldet)."""
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
