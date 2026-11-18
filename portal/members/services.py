"""Fachlogik der Mitgliederverwaltung: Sichtbarkeit, Verknüpfungen mit Benutzern, Zugänge für Mitglieder und Eltern."""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.db.models import QuerySet
from django.template.loader import render_to_string
from django.urls import reverse

from portal.accounts import services as accounts
from portal.accounts.models import Invitation, Role, User
from portal.core import audit

from .models import ADULT_AGE, OWN_ACCESS_AGE, LinkKind, Member, MemberLink, PendingLink

log = logging.getLogger(__name__)

# Wer Mitglieder sehen, anlegen, bearbeiten und importieren darf. Übungsleiter vorerst nicht (ADR 0009).
MANAGE_MEMBERS = (Role.DEPARTMENT_HEAD, Role.ADMIN)


def can_manage_members(user: Any) -> bool:
    return bool(user.is_authenticated and user.has_role(*MANAGE_MEMBERS))


def effective_links(user: Any) -> list[MemberLink]:
    """Verknüpfungen, die heute gelten: eigenes Profil zuerst, dann Kinder vom ältesten zum jüngsten."""
    if not user.is_authenticated or not user.is_active:
        return []
    links = MemberLink.objects.filter(user=user).select_related("member")
    effective = [link for link in links if link.is_effective()]
    return sorted(effective, key=lambda link: (link.kind != LinkKind.SELF, link.member.birth_date, link.member.pk))


def own_members(user: Any) -> list[Member]:
    """Mitglieder, die der Benutzer als eigene sieht: das eigene Profil und Kinder unter 18."""
    return [link.member for link in effective_links(user)]


def member_users(member: Member) -> list[User]:
    """Aktive Benutzer, für die das Mitglied heute ein eigenes ist (es selbst, Eltern bis 18)."""
    links = member.links.select_related("user").filter(user__is_active=True)
    return [link.user for link in links if link.is_effective()]


def guardians(member: Member) -> list[User]:
    """Eltern mit gültiger Verknüpfung (nur bis 18), z. B. als Notfallkontakt."""
    links = member.links.select_related("user").filter(user__is_active=True, kind=LinkKind.GUARDIAN)
    return [link.user for link in links if link.is_effective()]


def visible_members(user: Any) -> QuerySet[Member]:
    """Alle Mitglieder, die der Benutzer sehen darf: Abteilungsleitung alle, sonst die eigenen."""
    if can_manage_members(user):
        return Member.objects.all()
    return Member.objects.filter(pk__in=[member.pk for member in own_members(user)])


def can_view(user: Any, member: Member) -> bool:
    return visible_members(user).filter(pk=member.pk).exists()


def can_self_edit(user: Any, member: Member) -> bool:
    """Eigene Kontakt- und Judo-Daten pflegen: eigenes Profil und Kinder unter 18."""
    return any(own.pk == member.pk for own in own_members(user))


def parents_greeting(*, user: User | None = None, invitation: Invitation | None = None) -> str:
    """„Liebe Eltern von Mia und Ben“ für Erziehungsberechtigte (auch erst eingeladene); sonst ""."""
    if user is not None and user.pk:
        names = Member.objects.filter(links__user=user, links__kind=LinkKind.GUARDIAN)
    elif invitation is not None and invitation.pk:
        names = Member.objects.filter(pending_links__invitation=invitation, pending_links__kind=LinkKind.GUARDIAN)
    else:
        return ""
    first_names = list(names.order_by("birth_date", "first_name").values_list("first_name", flat=True).distinct())
    if not first_names:
        return ""
    joined = first_names[0] if len(first_names) == 1 else f"{', '.join(first_names[:-1])} und {first_names[-1]}"
    return f"Liebe Eltern von {joined}"


def link_kinds_for(member: Member) -> list[LinkKind]:
    """Welche Zugänge für ein Mitglied möglich sind: eigener ab 14, Eltern bis 18."""
    age = member.age()
    kinds = []
    if age >= OWN_ACCESS_AGE and not member.links.filter(kind=LinkKind.SELF).exists():
        kinds.append(LinkKind.SELF)
    if age < ADULT_AGE:
        kinds.append(LinkKind.GUARDIAN)
    return kinds


@transaction.atomic
def link(member: Member, user: User, kind: LinkKind | str, by: User | None = None) -> MemberLink:
    """Verknüpft Benutzer und Mitglied. Wer sein eigenes Profil verknüpft, bekommt die Rolle Mitglied."""
    kind = LinkKind(kind)
    if kind == LinkKind.SELF:
        if MemberLink.objects.filter(user=user, kind=LinkKind.SELF).exclude(member=member).exists():
            raise ValueError(f"{user.email} ist schon mit einem eigenen Mitgliedsprofil verknüpft.")
        if member.links.filter(kind=LinkKind.SELF).exclude(user=user).exists():
            raise ValueError(f"{member.display_name} hat schon einen eigenen Zugang.")
    member_link, _ = MemberLink.objects.update_or_create(user=user, member=member, defaults={"kind": kind})
    if kind == LinkKind.SELF and not user.has_role(Role.MEMBER):
        user.set_roles([*user.roles, Role.MEMBER])
    audit.log(
        by,
        audit.Area.MEMBERS,
        "link",
        f"{user.display_name} mit {member.display_name} verknüpft ({kind.label})",
        member=member,
        user=user,
    )
    log.info("%s mit Mitglied %s verknüpft (%s)", user.email, member.pk, kind.value)
    return member_link


def unlink(member_link: MemberLink, by: User | None = None) -> None:
    member_link.delete()
    audit.log(
        by,
        audit.Area.MEMBERS,
        "unlink",
        f"Verknüpfung {member_link.user.display_name} ↔ {member_link.member.display_name} gelöst",
        member=member_link.member_id,
        user=member_link.user_id,
    )
    log.info("Verknüpfung %s mit Mitglied %s gelöst", member_link.user.email, member_link.member.pk)


@transaction.atomic
def give_access(
    member: Member, email: str, kind: LinkKind | str, *, invited_by: User | None = None, send: bool = True
) -> tuple[str, Invitation | None]:
    """Zugang für ein Mitglied oder einen Elternteil.

    Gibt es zur Adresse schon einen aktiven Benutzer, wird er direkt verknüpft und per Mail benachrichtigt
    (``("linked", None)``). Sonst geht eine Einladung raus; die Verknüpfung entsteht beim Annehmen
    (``("invited", invitation)``). Offene Verknüpfungen früherer Einladungen an dieselbe Adresse bleiben erhalten.
    """
    kind = LinkKind(kind)
    email = email.strip().lower()
    user = User.objects.filter(email=email, is_active=True).first()
    if user is not None:
        link(member, user, kind, by=invited_by)
        transaction.on_commit(lambda: send_link_notice(user, member, kind))
        return "linked", None

    earlier = list(
        PendingLink.objects.filter(invitation__email=email, invitation__accepted_at__isnull=True).values_list(
            "member_id", "kind"
        )
    )
    first_name, last_name = (member.first_name, member.last_name) if kind == LinkKind.SELF else ("", "")
    invitation = accounts.invite(email, first_name=first_name, last_name=last_name, invited_by=invited_by, send=send)
    pending = {member_id: pending_kind for member_id, pending_kind in earlier}
    pending[member.pk] = kind
    audit.log(
        invited_by,
        audit.Area.MEMBERS,
        "invite",
        f"Einladung an {email} für {member.display_name} ({kind.label})",
        member=member,
    )
    PendingLink.objects.bulk_create(
        [PendingLink(invitation=invitation, member_id=member_id, kind=k) for member_id, k in pending.items()]
    )
    return "invited", invitation


def complete_pending_links(invitation: Invitation, user: User) -> None:
    """Beim Annehmen einer Einladung: vorgemerkte Verknüpfungen anlegen."""
    for pending in PendingLink.objects.filter(invitation=invitation).select_related("member"):
        try:
            link(pending.member, user, pending.kind, by=user)
        except ValueError:
            log.warning("Verknüpfung %s mit Mitglied %s übersprungen", user.email, pending.member.pk, exc_info=True)
        pending.delete()


def send_link_notice(user: User, member: Member, kind: LinkKind) -> None:
    """Kurze Mail an einen bestehenden Benutzer, der mit einem Mitglied verknüpft wurde."""
    context = {
        "user": user,
        "member": member,
        "kind": kind,
        "url": settings.BASE_URL + reverse("my_data"),
        "base_url": settings.BASE_URL,
    }
    message = EmailMultiAlternatives(
        subject=settings.EMAIL_SUBJECT_PREFIX + f"Neu verknüpft: {member.display_name}",
        body=render_to_string("members/email/link_notice.txt", context),
        to=[user.email],
    )
    message.attach_alternative(render_to_string("members/email/link_notice.html", context), "text/html")
    message.send()


# Protokoll (ADR 0015)

MEMBER_FIELDS = (
    "member_number",
    "first_name",
    "last_name",
    "birth_date",
    "gender",
    "joined_on",
    "left_on",
    "email",
    "phone",
    "grade",
    "weight",
    "interests",
)


def member_snapshot(member: Member | None) -> dict[str, Any] | None:
    return audit.snapshot(member, MEMBER_FIELDS) if member is not None and member.pk else None


def record_change(member: Member, before: dict[str, Any] | None, by: User | None, how: str = "") -> None:
    """Anlegen oder Ändern eines Mitglieds protokollieren; ``before`` aus ``member_snapshot`` vor dem Speichern."""
    after = audit.snapshot(member, MEMBER_FIELDS)
    suffix = f" ({how})" if how else ""
    if before is None:
        audit.log(by, audit.Area.MEMBERS, "create", f"{member.display_name} angelegt{suffix}", member=member)
        return
    changes = audit.diff(before, after, audit.labels_for(Member, MEMBER_FIELDS))
    if changes:
        fields = ", ".join(changes)
        audit.log(
            by,
            audit.Area.MEMBERS,
            "update",
            f"{member.display_name} geändert{suffix}: {fields}",
            member=member,
            changes=changes,
        )
