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
) -> Invitation:
    """Lädt eine Person ein. Offene Einladungen an dieselbe Adresse werden ersetzt."""
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
    transaction.on_commit(lambda: send_invitation(invitation))
    return invitation


def resend(invitation: Invitation) -> None:
    invitation.renew()
    send_invitation(invitation)


@transaction.atomic
def accept(invitation: Invitation, request: HttpRequest) -> User:
    """Nimmt die Einladung an: Konto anlegen bzw. ergänzen, Rollen setzen, anmelden."""
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
    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=["user", "accepted_at"])
    login(request, user, backend=AUTH_BACKEND)
    # Der Einladungslink belegt den Besitz der Mail-Adresse wie ein Anmeldecode. So kann die Person direkt
    # danach einen Passkey hinzufügen, ohne sich erneut bestätigen zu müssen.
    record_authentication(request, user, method="code", email=user.email, reauthenticated=True)
    return user


def ensure_initial_admin() -> Invitation | None:
    """Lädt PORTAL_INITIAL_ADMIN_EMAIL als Administrator ein, solange es keinen aktiven Administrator gibt."""
    email = (settings.INITIAL_ADMIN_EMAIL or "").strip().lower()
    if not email:
        return None
    if any(u.has_role(Role.ADMIN) for u in User.objects.filter(is_active=True)):
        return None
    open_invitation = Invitation.objects.filter(email=email, accepted_at__isnull=True).first()
    if open_invitation and open_invitation.is_valid:
        return None
    invitation = invite(email, roles=[Role.ADMIN])
    log.warning("Erster Administrator eingeladen: %s – Link: %s", email, invitation_url(invitation))
    return invitation
