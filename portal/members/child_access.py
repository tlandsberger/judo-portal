"""Eigener Zugang für Kinder ab 14, eingerichtet von den Eltern (ADR 0024).

Eltern geben die E-Mail-Adresse ihres Kindes ein, danach läuft die normale Einladung (``services.give_access``).
Die Startseite zeigt ein Banner, bis eine Einladung raus ist oder der Elternteil „Nicht jetzt“ wählt; zum 14.
Geburtstag geht einmal eine Mail an die Eltern.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from portal.accounts.models import Invitation, User

from . import services
from .models import ADULT_AGE, OWN_ACCESS_AGE, AccessOffer, LinkKind, Member, PendingLink

log = logging.getLogger(__name__)

# Fällt die nächtliche Mail einmal aus, holt der Job sie innerhalb dieser Frist nach. Kinder, die schon länger 14
# sind, bekommen keine Mail mehr (nur das Banner).
NOTIFY_DAYS = 7


class ChildAccessError(Exception):
    pass


def _in_age(member: Member, on: date | None = None) -> bool:
    return OWN_ACCESS_AGE <= member.age(on) < ADULT_AGE and member.is_active


def has_own_access(member: Member) -> bool:
    return member.links.filter(kind=LinkKind.SELF).exists()


def pending_invitation(member: Member) -> Invitation | None:
    """Offene, noch gültige Einladung für den eigenen Zugang des Mitglieds."""
    pending = (
        PendingLink.objects.filter(
            member=member,
            kind=LinkKind.SELF,
            invitation__accepted_at__isnull=True,
            invitation__expires_at__gt=timezone.now(),
        )
        .select_related("invitation")
        .order_by("-invitation__created_at")
        .first()
    )
    return pending.invitation if pending else None


def is_open(member: Member) -> bool:
    """Alt genug, noch ohne eigenen Zugang und ohne offene Einladung."""
    return _in_age(member) and not has_own_access(member) and pending_invitation(member) is None


def guardian_children(user: Any) -> list[Member]:
    """Kinder des Benutzers (gültige Verknüpfung „Erziehungsberechtigt“) im Alter für einen eigenen Zugang."""
    return [
        link.member
        for link in services.effective_links(user)
        if link.kind == LinkKind.GUARDIAN and _in_age(link.member)
    ]


def can_invite(user: Any, member: Member) -> bool:
    return any(child.pk == member.pk for child in guardian_children(user)) and not has_own_access(member)


def banner_children(user: Any) -> list[Member]:
    """Für die Startseite: Kinder, für die noch kein Zugang eingerichtet ist und deren Hinweis nicht weggeklickt ist."""
    children = [child for child in guardian_children(user) if is_open(child)]
    if not children:
        return []
    dismissed = set(
        AccessOffer.objects.filter(user=user, member__in=children, dismissed_at__isnull=False).values_list(
            "member_id", flat=True
        )
    )
    return [child for child in children if child.pk not in dismissed]


def dismiss(user: User, member: Member) -> None:
    AccessOffer.objects.update_or_create(member=member, user=user, defaults={"dismissed_at": timezone.now()})


def state(user: Any, member: Member) -> dict[str, Any] | None:
    """Für die Seite des Kindes unter „Meine Daten“: Stand des eigenen Zugangs (nur für Eltern, nur ab 14)."""
    if not any(child.pk == member.pk for child in guardian_children(user)):
        return None
    own = member.links.filter(kind=LinkKind.SELF).select_related("user").first()
    return {"own_user": own.user if own else None, "invitation": None if own else pending_invitation(member)}


def _check_email(member: Member, email: str) -> None:
    if User.objects.filter(email__iexact=email).exists():
        raise ChildAccessError(
            "Zu dieser Adresse gibt es schon einen Benutzer. Gib bitte die eigene Adresse von "
            f"{member.first_name} an. Hat {member.first_name} schon einen Benutzer, schreib uns kurz, "
            "dann verknüpfen wir ihn."
        )


@transaction.atomic
def invite_child(user: User, member: Member, email: str, *, sync_member: bool = False) -> Invitation:
    """Eltern laden ihr Kind ein. Eine frühere Einladung für den eigenen Zugang des Kindes wird ersetzt."""
    if not can_invite(user, member):
        raise ChildAccessError(f"Für {member.first_name} kannst du keinen Zugang einrichten.")
    email = email.strip().lower()
    _check_email(member, email)
    for earlier in PendingLink.objects.filter(
        member=member, kind=LinkKind.SELF, invitation__accepted_at__isnull=True
    ).select_related("invitation"):
        old = earlier.invitation
        earlier.delete()
        if not old.pending_links.exists() and not old.roles:
            old.delete()
    _, invitation = services.give_access(member, email, LinkKind.SELF, invited_by=user)
    if invitation is None:  # zur Adresse gibt es keinen Benutzer (oben geprüft)
        raise ChildAccessError("Die Einladung konnte nicht angelegt werden.")
    if sync_member and member.email != email:
        before = services.member_snapshot(member)
        member.email = email
        member.save(update_fields=["email", "updated_at"])
        services.record_change(member, before, user, "E-Mail-Adresse aus der Einladung übernommen")
    log.info("Eigener Zugang für Mitglied %s von Elternteil %s angefragt", member.pk, user.pk)
    return invitation


def child_access_url(member: Member) -> str:
    return settings.BASE_URL + reverse("child_access", args=[member.pk])


def send_birthday_notice(user: User, member: Member) -> None:
    context = {"user": user, "member": member, "url": child_access_url(member), "base_url": settings.BASE_URL}
    message = EmailMultiAlternatives(
        subject=settings.EMAIL_SUBJECT_PREFIX + f"{member.first_name} kann jetzt einen eigenen Zugang bekommen",
        body=render_to_string("members/email/child_access.txt", context),
        to=[user.email],
    )
    message.attach_alternative(render_to_string("members/email/child_access.html", context), "text/html")
    message.send()


def notify_birthdays(today: date | None = None) -> int:
    """Nächtlich: Eltern von Kindern, die in den letzten Tagen 14 geworden sind, einmal per Mail informieren."""
    today = today or timezone.localdate()
    earliest = today - timedelta(days=NOTIFY_DAYS)
    # Grob vorfiltern (14 bis 15 Jahre), genau prüft ``age``.
    candidates = Member.objects.filter(
        birth_date__lte=date(today.year - OWN_ACCESS_AGE + 1, 1, 1),
        birth_date__gte=date(today.year - OWN_ACCESS_AGE - 1, 1, 1),
    )
    sent = 0
    for member in candidates:
        if member.age(today) < OWN_ACCESS_AGE or member.age(earliest) >= OWN_ACCESS_AGE or not is_open(member):
            continue
        for guardian in services.guardians(member):
            offer, _ = AccessOffer.objects.get_or_create(member=member, user=guardian)
            if offer.notified_at is not None:
                continue
            try:
                send_birthday_notice(guardian, member)
            except Exception:
                log.exception("Hinweis auf eigenen Zugang an Benutzer %s nicht verschickt", guardian.pk)
                continue
            offer.notified_at = timezone.now()
            offer.save(update_fields=["notified_at"])
            sent += 1
    return sent


def run_daily() -> None:
    notify_birthdays()
