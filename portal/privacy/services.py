"""Datenschutz (ADR 0015): Auskunft, Löschen auf Wunsch und nach Austritt, Hinweis-Mails.

Kennt die Fach-Apps über deren Modelle und Services; umgekehrt kennt keine App diese hier.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from allauth.mfa.models import Authenticator
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from portal.accounts.models import Invitation, KnownDevice, Role, User
from portal.billing.models import Claim, Rate
from portal.core import audit
from portal.events.models import Participation
from portal.members import services as members
from portal.members.models import LinkKind, Member, MemberLink, PendingLink
from portal.notifications.models import PushNotificationSubscription, SentNotification

log = logging.getLogger(__name__)

CONTACT = "judo@wedeler-tsv.de"
DELETE_AFTER_MONTHS = 3
SOON_DAYS = 30
# Wer eine dieser Rollen hat, bleibt als Benutzer, auch ohne Mitglied.
FUNCTION_ROLES = (Role.TRAINER, Role.DEPARTMENT_HEAD, Role.ADMIN)


def can_manage(user: Any) -> bool:
    """Protokoll, Auskunft für jedes Mitglied und Löschen: Abteilungsleitung und Admin."""
    return members.can_manage_members(user)


# Fristen


def _add_months(day: date, months: int) -> date:
    index = day.year * 12 + day.month - 1 + months
    year, month = index // 12, index % 12 + 1
    for last in (31, 30, 29, 28):
        try:
            return date(year, month, min(day.day, last))
        except ValueError:
            continue
    raise ValueError(day)


def deletion_date(member: Member) -> date | None:
    """Tag, an dem ein ausgetretenes Mitglied gelöscht wird: drei Monate nach dem Austritt."""
    return _add_months(member.left_on, DELETE_AFTER_MONTHS) if member.left_on else None


def due_for_deletion(today: date | None = None) -> list[Member]:
    today = today or timezone.localdate()
    candidates = Member.objects.filter(left_on__isnull=False, left_on__lte=today)
    return [member for member in candidates if deletion_date(member) <= today]  # type: ignore[operator]


def deleted_soon(today: date | None = None, days: int = SOON_DAYS) -> list[tuple[Member, date]]:
    """Für die Mitgliederliste: wer in den nächsten ``days`` Tagen gelöscht wird."""
    today = today or timezone.localdate()
    rows = []
    for member in Member.objects.filter(left_on__isnull=False).order_by("left_on"):
        when = deletion_date(member)
        if when is not None and (when - today).days <= days:
            rows.append((member, when))
    return rows


# Hinweis zum Austritt


def _users_of(member: Member) -> list[User]:
    """Alle Zugänge eines Mitglieds: eigenes Profil und verknüpfte Eltern (auch nach dem 18. Geburtstag)."""
    links = MemberLink.objects.filter(member=member, user__is_active=True).select_related("user")
    return sorted({link.user for link in links}, key=lambda user: user.pk)


def _send(user: User, subject: str, template: str, context: dict[str, Any]) -> None:
    context = {"user": user, "base_url": settings.BASE_URL, **context}
    message = EmailMultiAlternatives(
        subject=settings.EMAIL_SUBJECT_PREFIX + subject,
        body=render_to_string(f"privacy/email/{template}.txt", context),
        to=[user.email],
    )
    message.attach_alternative(render_to_string(f"privacy/email/{template}.html", context), "text/html")
    message.send()


def send_deletion_notices(today: date | None = None) -> int:
    """Am Austrittsdatum (oder beim ersten Lauf danach) alle Zugänge über die Löschung informieren, einmal."""
    today = today or timezone.localdate()
    rows = Member.objects.filter(left_on__isnull=False, left_on__lte=today, deletion_notice_sent_at__isnull=True)
    count = 0
    for member in rows:
        when = deletion_date(member)
        url = settings.BASE_URL + reverse("my_privacy")
        for user in _users_of(member):
            own = MemberLink.objects.filter(member=member, user=user, kind=LinkKind.SELF).exists()
            _send(
                user,
                "Austritt: deine Daten im Portal",
                "deletion_notice",
                {"member": member, "own": own, "when": when, "url": url},
            )
            count += 1
        Member.objects.filter(pk=member.pk).update(deletion_notice_sent_at=timezone.now())
        audit.log(
            None,
            audit.Area.PRIVACY,
            "deletion_notice",
            f"Hinweis zur Löschung am {when:%d.%m.%Y} an {len(_users_of(member))} Zugänge verschickt",
            member=member,
        )
    return count


# Löschen


@dataclass
class DeletionPreview:
    member: Member
    participations: int
    claims: int
    links: list[MemberLink]
    users_deleted: list[User] = field(default_factory=list)


def _orphaned_users(member: Member) -> list[User]:
    """Benutzer, die nach dem Löschen kein Mitglied mehr haben und keine Funktionsrolle."""
    result = []
    for link in MemberLink.objects.filter(member=member).select_related("user"):
        user = link.user
        others = MemberLink.objects.filter(user=user).exclude(member=member).exists()
        pending = PendingLink.objects.filter(invitation__user=user).exclude(member=member).exists()
        if not others and not pending and not any(role in user.roles for role in FUNCTION_ROLES):
            result.append(user)
    return result


def preview_deletion(member: Member) -> DeletionPreview:
    return DeletionPreview(
        member=member,
        participations=Participation.objects.filter(member=member).count(),
        claims=Claim.objects.filter(member=member).count(),
        links=list(MemberLink.objects.filter(member=member).select_related("user")),
        users_deleted=_orphaned_users(member),
    )


def delete_user(user: User, by: User | None, reason: str) -> None:
    """Benutzer mit Anmeldewegen, Geräten und Benachrichtigungen löschen; vorher eine Mail."""
    email, name = user.email, user.display_name
    # Wer sich selbst löscht, kann nicht mehr als Handelnder im Protokoll stehen.
    actor = None if by is not None and by.pk == user.pk else by
    transaction.on_commit(lambda: _send_user_deleted(email, name, reason))
    audit.forget_user(user.pk)
    user.delete()
    audit.log(actor, audit.Area.PRIVACY, "user_deleted", f"Benutzer gelöscht ({reason})")


def _send_user_deleted(email: str, name: str, reason: str) -> None:
    context = {"name": name, "reason": reason, "base_url": settings.BASE_URL}
    message = EmailMultiAlternatives(
        subject=settings.EMAIL_SUBJECT_PREFIX + "Dein Zugang wurde gelöscht",
        body=render_to_string("privacy/email/user_deleted.txt", context),
        to=[email],
    )
    message.attach_alternative(render_to_string("privacy/email/user_deleted.html", context), "text/html")
    message.send()


REASON_SELF = "auf eigenen Wunsch"


class DeletionError(Exception):
    """Löschen ist so nicht möglich; die Nachricht ist für die Oberfläche."""


def check_own_deletion(user: User) -> None:
    """Den eigenen Zugang darf jeder löschen, nur nicht der letzte aktive Administrator."""
    if user.has_role(Role.ADMIN):
        admins = [other for other in User.objects.filter(is_active=True) if other.has_role(Role.ADMIN)]
        if len(admins) <= 1:
            raise DeletionError("Du bist der einzige Administrator. Gib die Rolle erst jemand anderem.")


@transaction.atomic
def delete_own_access(user: User) -> list[Member]:
    """Eigenen Zugang löschen (z. B. Kind volljährig). Die Mitglieder bleiben und können neu eingeladen werden."""
    check_own_deletion(user)
    kept = [link.member for link in MemberLink.objects.filter(user=user).select_related("member")]
    for member in kept:
        audit.log(
            None,
            audit.Area.MEMBERS,
            "unlink",
            f"Zugang {user.email} zu {member.display_name} selbst gelöscht",
            member=member,
        )
    delete_user(user, user, REASON_SELF)
    return kept


REASON_LEFT = "nach Austritt"
REASON_REQUEST = "auf Wunsch"


@transaction.atomic
def delete_member(member: Member, by: User | None, reason: str) -> DeletionPreview:
    """Mitglied mit allem löschen: Teilnahmen, Abrechnungen, Sätze, Verknüpfungen, Protokoll; verwaiste Benutzer.

    Übrig bleibt ein Protokolleintrag mit der Mitgliedsnummer, ohne Name und weitere Daten.
    """
    result = preview_deletion(member)
    number = f"Nr. {member.member_number}" if member.member_number else "ohne Nummer"
    # Erst die Abrechnungen (ihre Zeilen schützen die Teilnahmen), dann das Mitglied mit allem, was dranhängt.
    Claim.objects.filter(member=member).delete()
    Rate.objects.filter(member=member).delete()
    PendingLink.objects.filter(member=member).delete()
    member_id = member.pk
    member.delete()
    audit.forget_member(member_id)
    for user in result.users_deleted:
        delete_user(user, by, "kein verknüpftes Mitglied mehr")
    audit.log(by, audit.Area.PRIVACY, "member_deleted", f"Mitglied {number} gelöscht ({reason})")
    log.info("Mitglied %s gelöscht (%s)", member_id, reason)
    return result


def run_daily(today: date | None = None) -> None:
    """Nächtlich: Hinweise zum Austritt, Löschen nach der Frist."""
    today = today or timezone.localdate()
    send_deletion_notices(today)
    for member in due_for_deletion(today):
        delete_member(member, None, REASON_LEFT)


# Auskunft


def _value(value: Any) -> Any:
    if isinstance(value, datetime):
        return timezone.localtime(value).strftime("%d.%m.%Y %H:%M")
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    if value is None or isinstance(value, bool | int | str):
        return value
    if isinstance(value, Decimal):
        return str(value).replace(".", ",")
    return str(value)


def _row(instance: Any, fields: list[str]) -> dict[str, Any]:
    return {
        str(instance._meta.get_field(name).verbose_name): _value(
            getattr(instance, f"get_{name}_display")()
            if getattr(instance._meta.get_field(name), "choices", None)
            else getattr(instance, name)
        )
        for name in fields
    }


def _audit_rows(rows: Any) -> list[dict[str, Any]]:
    result = []
    for entry in rows[:500]:
        row = {
            "Zeitpunkt": _value(entry.at),
            "Von": entry.who,
            "Bereich": entry.get_area_display(),
            "Beschreibung": entry.summary,
        }
        changes = []
        for field_name, values in (entry.changes or {}).items():
            old, new = [*values, None, None][:2] if isinstance(values, list) else (None, values)
            changes.append(f"{field_name}: {old or '–'} → {new or '–'}")
        row["Änderungen"] = "; ".join(changes)
        result.append(row)
    return result


def export_member(member: Member) -> dict[str, Any]:
    """Alles zu einem Mitglied."""
    data: dict[str, Any] = {
        "Stammdaten": _row(
            member,
            [
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
            ],
        )
        | {"Angelegt am": _value(member.created_at), "Zuletzt geändert": _value(member.updated_at)},
        "Interessen": [str(interest) for interest in member.interests.all()],
        "Zugänge": [
            {"Benutzer": link.user.email, "Art": link.get_kind_display(), "Seit": _value(link.created_at)}
            for link in member.links.select_related("user")
        ],
        "Teilnahmen": [
            {
                "Veranstaltung": p.occurrence.event.title,
                "Beginn": _value(p.occurrence.starts_at),
                "Rolle": p.role.name,
                "Status": p.get_status_display(),
                "Gewicht": _value(p.weight),
                "Hinweis": p.note,
                "Stunden bestätigt": _value(p.confirmed_at),
                "Minuten": p.minutes,
            }
            for p in member.participations.select_related("occurrence__event", "role").order_by(
                "-occurrence__starts_at"
            )
        ],
        "Stundensätze": [
            {"Rolle": rate.role.name, "Satz": _value(rate.hourly_rate), "Gültig ab": _value(rate.valid_from)}
            for rate in Rate.objects.filter(member=member).select_related("role")
        ],
        "Abrechnungen": [
            {
                "Monat": claim.month_label,
                "Status": claim.get_status_display(),
                "Verspätet": claim.is_late,
                "Minuten": claim.total_minutes,
                "Betrag": _value(claim.total_amount),
                "Zeilen": [
                    {
                        "Datum": _value(line.day),
                        "Veranstaltung": line.event_title,
                        "Rolle": line.role_name,
                        "Minuten": line.minutes,
                        "Satz": _value(line.hourly_rate),
                        "Betrag": _value(line.amount),
                    }
                    for line in claim.lines.all()
                ],
            }
            for claim in Claim.objects.filter(member=member)
        ],
        "Protokoll": _audit_rows(audit.entries(member_id=member.pk)),
    }
    if deletion_date(member):
        data["Löschung geplant am"] = _value(deletion_date(member))
    return data


def export_user(user: User) -> dict[str, Any]:
    """Alles zum Benutzer selbst (ohne Geheimnisse wie Passwort-Hash oder Passkey-Schlüssel)."""
    return {
        "Benutzer": {
            "E-Mail": user.email,
            "Vorname": user.first_name,
            "Nachname": user.last_name,
            "Telefon": user.phone,
            "Rollen": user.role_labels,
            "Angelegt am": _value(user.date_joined),
            "Zuletzt angemeldet": _value(user.last_login),
        },
        "Anmeldewege": {
            "Passwort": user.has_usable_password(),
            "Passkeys": [
                {
                    "Name": str(a.wrap().name),
                    "Angelegt": _value(a.created_at),
                    "Zuletzt benutzt": _value(a.last_used_at),
                }
                for a in Authenticator.objects.filter(user=user, type=Authenticator.Type.WEBAUTHN)
            ],
        },
        "Bekannte Geräte": [
            {"Gerät": d.description, "Zuerst": _value(d.first_seen), "Zuletzt": _value(d.last_seen)}
            for d in KnownDevice.objects.filter(user=user)
        ],
        "Geräte für Push-Benachrichtigungen": [
            {"Gerät": s.device, "Eingerichtet": _value(s.created_at), "Zuletzt genutzt": _value(s.last_used_at)}
            for s in PushNotificationSubscription.objects.filter(user=user)
        ],
        "Benachrichtigungen": [
            {"Zeitpunkt": _value(n.created_at), "Anlass": n.kind, "Titel": n.title, "Kanal": n.get_channel_display()}
            for n in SentNotification.objects.filter(user=user).order_by("-created_at")[:500]
        ],
        "Einladungen": [
            {"Angelegt": _value(i.created_at), "Angenommen": _value(i.accepted_at)}
            for i in Invitation.objects.filter(user=user)
        ],
        # Nur Einträge über den Benutzer selbst – nicht, was er (z. B. als Abteilungsleitung) bei anderen geändert hat.
        "Protokoll": _audit_rows(audit.AuditEntry.objects.filter(user_id=user.pk, member_id__isnull=True)),
    }


def export(user: User) -> dict[str, Any]:
    """Auskunft für „Meine Daten“: der Benutzer und alle Mitglieder, die er sieht (eigenes Profil, Kinder unter 18)."""
    return {
        "Erstellt am": _value(timezone.now()),
        "Hinweis": f"Auskunft von Wedeler TSV Judo (Art. 15 DSGVO). Fragen an {CONTACT}.",
        **export_user(user),
        "Mitglieder": {member.display_name: export_member(member) for member in members.own_members(user)},
    }
