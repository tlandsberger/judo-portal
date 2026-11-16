"""Benachrichtigungen der Abrechnung über ``portal.notifications`` (Push, sonst Mail; ADR 0011, 0014).

Sofort: eingereicht (an die Abteilungsleitung), freigegeben oder zurückgegeben (an den Übungsleiter). Am 1. des
Monats: Erinnerung an den Vormonat und an den Monat, dessen Frist am 5. endet.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from django.urls import reverse
from django.utils import formats, timezone

from portal.accounts.models import Role, User
from portal.events import services as events
from portal.notifications import services as notifications

if TYPE_CHECKING:
    from .models import Claim

REMIND_DAY = 1
REMIND_HOUR = 9


def _heads() -> list[User]:
    users = User.objects.filter(is_active=True).order_by("pk")
    heads = [user for user in users if user.has_role(Role.DEPARTMENT_HEAD)]
    return heads or [user for user in users if user.has_role(Role.ADMIN)]


def submitted(claim: Claim) -> None:
    stamp = int(claim.submitted_at.timestamp())
    url = reverse("claim_detail", args=[claim.pk])
    for user in _heads():
        notifications.notify(
            user,
            key=f"claim-submitted:{claim.pk}:{user.pk}:{stamp}",
            kind="claim_submitted",
            title=f"Abrechnung {claim.month_label}",
            body=f"{claim.member.display_name} hat {claim.month_label} eingereicht "
            f"({formats.number_format(claim.hours, 2)} Stunden){' – verspätet' if claim.is_late else ''}.",
            url=url,
        )


def decided(claim: Claim) -> None:
    user = events.member_user(claim.member)
    if user is None or claim.decided_at is None:
        return
    if claim.status == "approved":
        title, body = f"Freigegeben: {claim.month_label}", f"Deine Abrechnung für {claim.month_label} ist freigegeben."
    else:
        title = f"Zurückgegeben: {claim.month_label}"
        body = f"Deine Abrechnung für {claim.month_label} kam zurück: {claim.feedback}"
    notifications.notify(
        user,
        key=f"claim-decided:{claim.pk}:{int(claim.decided_at.timestamp())}",
        kind="claim_decided",
        title=title,
        body=body,
        url=reverse("billing_month", args=[claim.month.year, claim.month.month]),
    )


def remind(today: date | None = None) -> None:
    """Am 1.: Vormonat einreichen; dazu letzte Erinnerung für den Monat, dessen Frist am 5. endet."""
    from . import services

    today = today or timezone.localdate()
    if today.day != REMIND_DAY:
        return
    previous = services.add_months(services.first_of_month(today), -1)
    for month, last in ((previous, False), (services.months_due(today), True)):
        label = formats.date_format(month, "F")
        until = formats.date_format(services.deadline(month), "j. F")
        for member in services.unsubmitted(month):
            user = events.member_user(member)
            if user is None:
                continue
            if last:
                title = f"Frist bis {until}: {label}"
                body = f"Deine Stunden aus {label} reichst du bitte bis zum {until} ein."
            else:
                title = f"Abrechnung {label}"
                body = f"Deine Stunden aus {label} sind bereit zum Einreichen (bis {until})."
            notifications.notify(
                user,
                key=f"claim-remind:{member.pk}:{month:%Y-%m}:{'last' if last else 'first'}",
                kind="claim_remind",
                title=title,
                body=body,
                url=reverse("billing_month", args=[month.year, month.month]),
            )


def run_remind() -> None:
    """Läuft alle 10 Minuten; erinnert wird tagsüber, je Monat und Anlass nur einmal."""
    if timezone.localtime().hour >= REMIND_HOUR:
        remind()


def register_all() -> None:
    from portal.core import scheduler

    scheduler.register_periodic(run_remind)
