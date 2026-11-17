"""Fachlogik der Übungsleiterabrechnung (ADR 0014).

Grundlage sind die bestätigten Stunden abrechnungsrelevanter Rollen aus ``portal.events``. Abgerechnet wird je
Übungsleiter und Monat; Frist ist der 5. des dritten Folgemonats (Januar bis 5. April). Danach lässt sich weiter
einreichen, die Abrechnung ist dann „verspätet“ und die Abteilungsleitung entscheidet über die Ausnahme. Beim
Einreichen werden Minuten, Satz und Betrag als Zeilen eingefroren; bis zum Zurückgeben sind die Termine gesperrt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from portal.accounts.models import Role, User
from portal.core import audit
from portal.events import services as events
from portal.events.models import ParticipantRole, Participation, ParticipationStatus
from portal.members.models import LinkKind, Member, MemberLink

from . import notices
from .models import Claim, ClaimLine, ClaimStatus, Rate, month_label

# Frist: der 5. des dritten Folgemonats
DEADLINE_MONTHS = 3
DEADLINE_DAY = 5
DECIDE = (Role.DEPARTMENT_HEAD, Role.ADMIN)
CENT = Decimal("0.01")


class BillingError(Exception):
    """Einreichen oder Entscheiden ist gerade nicht möglich; die Nachricht ist für die Oberfläche."""


# Monate


def first_of_month(day: date) -> date:
    return day.replace(day=1)


def add_months(month: date, count: int) -> date:
    index = month.year * 12 + month.month - 1 + count
    return date(index // 12, index % 12 + 1, 1)


def month_range(month: date) -> tuple[datetime, datetime]:
    """Beginn und Ende des Monats in Ortszeit, als bewusste Zeitpunkte."""
    tz = timezone.get_current_timezone()
    start = datetime.combine(month, datetime.min.time(), tzinfo=tz)
    end = datetime.combine(add_months(month, 1), datetime.min.time(), tzinfo=tz)
    return start, end


def deadline(month: date) -> date:
    """Letzter Tag, um ``month`` fristgerecht einzureichen: der 5. des dritten Folgemonats (Januar → 5. April)."""
    return add_months(first_of_month(month), DEADLINE_MONTHS).replace(day=DEADLINE_DAY)


def is_overdue(month: date, today: date | None = None) -> bool:
    return (today or timezone.localdate()) > deadline(month)


def months_due(today: date | None = None) -> date:
    """Der Monat, dessen Frist im laufenden Monat endet (im April: Januar)."""
    return add_months(first_of_month(today or timezone.localdate()), -DEADLINE_MONTHS)


def month_of(participation: Participation) -> date:
    return first_of_month(timezone.localdate(participation.occurrence.starts_at))


# Sätze


def rate_for(member: Member, role: ParticipantRole, day: date) -> Rate | None:
    """Der am Termintag gültige Satz für diese Rolle. Ohne Satz lässt sich die Rolle nicht abrechnen."""
    return Rate.objects.filter(member=member, role=role, valid_from__lte=day).order_by("-valid_from").first()


def amount(minutes: int, hourly_rate: Decimal) -> Decimal:
    """Betrag einer Zeile, kaufmännisch auf Cent gerundet."""
    return (Decimal(minutes) * hourly_rate / 60).quantize(CENT, rounding=ROUND_HALF_UP)


def billable_roles() -> list[ParticipantRole]:
    return list(ParticipantRole.objects.filter(is_billable=True, is_active=True))


@dataclass
class RateRow:
    """Eine Zeile der Seite „Stundensätze“: ein Übungsleiter mit dem aktuellen Satz je Rolle (``None`` = fehlt)."""

    member: Member
    user: User
    rates: list[tuple[ParticipantRole, Rate | None]]

    @property
    def missing(self) -> bool:
        return any(rate is None for _, rate in self.rates)


def rate_table(today: date | None = None) -> list[RateRow]:
    """Alle, die abrechnungsrelevante Team-Rollen übernehmen können, mit ihrem heute gültigen Satz je Rolle."""
    today = today or timezone.localdate()
    roles = [role for role in billable_roles() if role.is_team]
    rows = []
    links = MemberLink.objects.filter(kind=LinkKind.SELF, user__is_active=True).select_related("member", "user")
    for link in links.order_by("member__last_name", "member__first_name"):
        own = [role for role in roles if events.user_may_take(link.user, role)]
        if not own:
            continue
        rows.append(RateRow(link.member, link.user, [(role, rate_for(link.member, role, today)) for role in own]))
    return rows


def rate_history(member: Member) -> QuerySet[Rate]:
    return Rate.objects.filter(member=member).select_related("role").order_by("role__order", "-valid_from")


# Monatsübersicht


def billable_participations(member: Member, month: date) -> QuerySet[Participation]:
    """Abrechnungsrelevante Teilnahmen des Monats (bestätigt oder nicht), ohne abgesagte Termine."""
    start, end = month_range(month)
    return (
        Participation.objects.filter(
            member=member,
            role__is_billable=True,
            status=ParticipationStatus.REGISTERED,
            occurrence__cancelled_at__isnull=True,
            occurrence__starts_at__gte=start,
            occurrence__starts_at__lt=end,
        )
        .select_related("occurrence__event", "role")
        .order_by("occurrence__starts_at")
    )


@dataclass
class Line:
    """Zeile einer noch nicht eingereichten Abrechnung (berechnet, nicht gespeichert)."""

    participation: Participation
    rate: Rate | None

    @property
    def day(self) -> date:
        return timezone.localdate(self.participation.occurrence.starts_at)

    @property
    def event_title(self) -> str:
        return self.participation.occurrence.event.title

    @property
    def role_name(self) -> str:
        return self.participation.role.name

    @property
    def minutes(self) -> int:
        return self.participation.minutes or 0

    @property
    def hourly_rate(self) -> Decimal | None:
        return self.rate.hourly_rate if self.rate else None

    @property
    def amount(self) -> Decimal | None:
        return amount(self.minutes, self.rate.hourly_rate) if self.rate else None


@dataclass
class Month:
    """Ein Monat eines Übungsleiters: eingereicht (``claim``) oder offen mit berechneten Zeilen."""

    member: Member
    month: date
    claim: Claim | None = None
    lines: list[Any] = field(default_factory=list)
    unconfirmed: list[Participation] = field(default_factory=list)
    missing_roles: list[str] = field(default_factory=list)
    can_submit: bool = False

    @property
    def label(self) -> str:
        return month_label(self.month)

    @property
    def status(self) -> str:
        """läuft, offen, überfällig, eingereicht, zurückgegeben, freigegeben."""
        if self.claim:
            return self.claim.get_status_display()
        if self.month >= first_of_month(timezone.localdate()):
            return "läuft"
        return "überfällig" if is_overdue(self.month) else "offen"

    @property
    def is_open(self) -> bool:
        return self.claim is None or self.claim.status == ClaimStatus.RETURNED

    @property
    def pending(self) -> list[Participation]:
        """Vergangene, noch nicht bestätigte Termine (kommende lassen sich noch nicht bestätigen)."""
        now = timezone.now()
        return [p for p in self.unconfirmed if p.occurrence.starts_at <= now] if self.is_open else []

    @property
    def total_minutes(self) -> int:
        return sum(line.minutes for line in self.lines)

    @property
    def hours(self) -> Decimal:
        return (Decimal(self.total_minutes) / 60).quantize(CENT)

    @property
    def total_amount(self) -> Decimal:
        return sum((line.amount or Decimal(0) for line in self.lines), Decimal(0))

    @property
    def deadline(self) -> date:
        return deadline(self.month)

    @property
    def is_overdue(self) -> bool:
        return is_overdue(self.month)


def month_overview(member: Member, month: date, today: date | None = None) -> Month:
    month = first_of_month(month)
    claim = Claim.objects.filter(member=member, month=month).first()
    result = Month(member, month, claim)
    if claim and claim.status != ClaimStatus.RETURNED:
        result.lines = list(claim.lines.all())
        return result
    rows = list(billable_participations(member, month))
    result.unconfirmed = [p for p in rows if not p.is_confirmed]
    result.lines = [Line(p, rate_for(member, p.role, timezone.localdate(p.occurrence.starts_at))) for p in rows]
    result.lines = [line for line in result.lines if line.participation.is_confirmed]
    result.missing_roles = sorted({line.role_name for line in result.lines if line.rate is None})
    finished = month < first_of_month(today or timezone.localdate())
    result.can_submit = bool(result.lines) and not result.missing_roles and finished
    return result


def months(member: Member, today: date | None = None) -> list[Month]:
    """Monate mit abrechnungsrelevanten Terminen oder einer Abrechnung, neuester zuerst (Termine ein Jahr zurück)."""
    today = today or timezone.localdate()
    current = first_of_month(today)
    found = set(Claim.objects.filter(member=member).values_list("month", flat=True))
    start, _ = month_range(add_months(current, -12))
    # Auch Monate, in denen nur noch unbestätigte Termine stehen: dort wird bestätigt und dann eingereicht.
    shifts = Participation.objects.filter(
        Q(confirmed_at__isnull=False) | Q(status=ParticipationStatus.REGISTERED),
        member=member,
        role__is_billable=True,
        occurrence__cancelled_at__isnull=True,
        occurrence__starts_at__gte=start,
        occurrence__starts_at__lte=timezone.now(),
    ).values_list("occurrence__starts_at", flat=True)
    found.update(first_of_month(timezone.localdate(starts)) for starts in shifts)
    found.add(current)
    return [month_overview(member, month, today) for month in sorted(found, reverse=True)]


def pending_confirmations(overviews: list[Month]) -> list[Participation]:
    """Vergangene, noch nicht bestätigte Termine aller offenen Monate, ältester zuerst."""
    return sorted((p for m in overviews for p in m.pending), key=lambda p: p.occurrence.starts_at)


# Ablauf


@transaction.atomic
def submit(member: Member, month: date, by: User, today: date | None = None) -> Claim:
    """Monat einreichen: Zeilen einfrieren, Termine sperren, Abteilungsleitung benachrichtigen.

    Nach der Frist wird die Abrechnung als verspätet markiert (beim ersten Einreichen; nach dem Zurückgeben bleibt
    die Markierung, wie sie war). Ob die Ausnahme gilt, entscheidet die Abteilungsleitung beim Freigeben.
    """
    today = today or timezone.localdate()
    overview = month_overview(member, month, today)
    if overview.claim and overview.claim.status != ClaimStatus.RETURNED:
        raise BillingError(f"{overview.label} ist schon eingereicht.")
    if first_of_month(month) >= first_of_month(today):
        raise BillingError("Einreichen kannst du erst nach Monatsende.")
    if not overview.can_submit:
        if overview.missing_roles:
            roles = ", ".join(overview.missing_roles)
            raise BillingError(f"Für {roles} ist noch kein Satz hinterlegt – sag der Abteilungsleitung Bescheid.")
        raise BillingError(f"Für {overview.label} sind keine Stunden bestätigt.")
    claim = overview.claim or Claim(member=member, month=overview.month, is_late=is_overdue(overview.month, today))
    claim.status = ClaimStatus.SUBMITTED
    claim.submitted_at = timezone.now()
    claim.submitted_by = by
    claim.decided_at = None
    claim.decided_by = None
    claim.decided_by_name = ""
    claim.total_minutes = overview.total_minutes
    claim.total_amount = overview.total_amount
    claim.save()
    claim.lines.all().delete()
    ClaimLine.objects.bulk_create(
        ClaimLine(
            claim=claim,
            participation=line.participation,
            day=line.day,
            event_title=line.event_title[:200],
            role_name=line.role_name[:60],
            minutes=line.minutes,
            hourly_rate=line.hourly_rate,
            amount=line.amount,
        )
        for line in overview.lines
    )
    late = " (verspätet)" if claim.is_late else ""
    audit.log(
        by,
        audit.Area.BILLING,
        "submit",
        f"Abrechnung {claim.month_label} von {member.display_name} eingereicht{late}: "
        f"{claim.total_minutes} Minuten, {claim.total_amount} €",
        member=member,
    )
    transaction.on_commit(lambda: notices.submitted(claim))
    return claim


def can_decide(user: Any) -> bool:
    """Freigeben und zurückgeben: Abteilungsleitung und Admin, auch für die eigene Abrechnung (ADR 0014)."""
    return bool(user.is_authenticated and user.has_role(*DECIDE))


def _decide(claim: Claim, by: User, status: ClaimStatus, feedback: str = "") -> None:
    if claim.status != ClaimStatus.SUBMITTED:
        raise BillingError("Die Abrechnung ist nicht (mehr) eingereicht.")
    claim.status = status
    claim.decided_at = timezone.now()
    claim.decided_by = by
    claim.decided_by_name = by.display_name
    claim.feedback = feedback
    claim.save(update_fields=["status", "decided_at", "decided_by", "decided_by_name", "feedback"])
    verb = "freigegeben" if status == ClaimStatus.APPROVED else f"zurückgegeben: {feedback}"
    audit.log(
        by,
        audit.Area.BILLING,
        "approve" if status == ClaimStatus.APPROVED else "send_back",
        f"Abrechnung {claim.month_label} von {claim.member.display_name} {verb}",
        member=claim.member_id,
    )


@transaction.atomic
def approve(claim: Claim, by: User) -> None:
    _decide(claim, by, ClaimStatus.APPROVED)
    transaction.on_commit(lambda: notices.decided(claim))


@transaction.atomic
def send_back(claim: Claim, by: User, feedback: str) -> None:
    """Zurückgeben: die Termine sind wieder offen, der Übungsleiter korrigiert und reicht erneut ein."""
    if not feedback.strip():
        raise BillingError("Schreib bitte kurz, was geändert werden soll.")
    _decide(claim, by, ClaimStatus.RETURNED, feedback.strip())
    transaction.on_commit(lambda: notices.decided(claim))


# Überblick für die Abteilungsleitung


def claims(month: date | None = None, status: str | None = None) -> QuerySet[Claim]:
    rows = Claim.objects.select_related("member")
    if month:
        rows = rows.filter(month=first_of_month(month))
    if status:
        rows = rows.filter(status=status)
    return rows.order_by("-month", "member__last_name", "member__first_name")


def pending_claims() -> QuerySet[Claim]:
    return claims(status=ClaimStatus.SUBMITTED)


def claim_months() -> list[date]:
    return list(Claim.objects.order_by("-month").values_list("month", flat=True).distinct())


def approved_for_month(month: date) -> QuerySet[Claim]:
    return claims(month, ClaimStatus.APPROVED)


# Sperre in portal.events


def lock_reason(participation: Participation) -> str | None:
    """Termine eines eingereichten oder freigegebenen Monats lassen sich nicht mehr bestätigen oder ändern."""
    if participation.member_id is None or not participation.role.is_billable:
        return None
    locked = Claim.objects.filter(member_id=participation.member_id, month=month_of(participation)).exclude(
        status=ClaimStatus.RETURNED
    )
    if locked.exists():
        return f"{month_label(month_of(participation))} ist schon zur Abrechnung eingereicht."
    return None


def is_locked(participation: Participation) -> bool:
    return lock_reason(participation) is not None


def locked_months(member: Member) -> set[date]:
    """Für Listen: die gesperrten Monate eines Mitglieds in einer Abfrage."""
    rows = Claim.objects.filter(member=member).exclude(status=ClaimStatus.RETURNED)
    return set(rows.values_list("month", flat=True))


# Erinnerungen


def unsubmitted(month: date) -> list[Member]:
    """Mitglieder mit bestätigten, nicht eingereichten Stunden in ``month``."""
    start, end = month_range(month)
    submitted = Claim.objects.filter(month=month).exclude(status=ClaimStatus.RETURNED).values("member_id")
    ids = (
        Participation.objects.filter(
            role__is_billable=True,
            confirmed_at__isnull=False,
            occurrence__cancelled_at__isnull=True,
            occurrence__starts_at__gte=start,
            occurrence__starts_at__lt=end,
        )
        .exclude(Q(member__isnull=True) | Q(member_id__in=submitted))
        .values_list("member_id", flat=True)
        .distinct()
    )
    return list(Member.objects.filter(pk__in=ids))


def register_all() -> None:
    events.register_lock(lock_reason)
