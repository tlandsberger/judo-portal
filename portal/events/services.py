"""Fachlogik der Veranstaltungen: Zielgruppen, Termine aus Zeitplänen, Teilnahme mit Rollen und Warteliste, Rechte.

Auf Mitglieder greift das Modul nur über ``portal.members.services`` zu (eigene Mitglieder, Eltern).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import IntEnum
from typing import Any

from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from portal.accounts.models import Role, User
from portal.members import services as members
from portal.members.models import LinkKind, Member, MemberLink, grade_rank

from . import notices
from .models import (
    Event,
    Guest,
    Occurrence,
    ParticipantRole,
    Participation,
    ParticipationStatus,
    Schedule,
    ScheduleTeam,
    TargetGroup,
)

log = logging.getLogger(__name__)

# Veranstaltungen, Zeitpläne, Zielgruppen, Arten und Rollen pflegt die Abteilungsleitung (ADR 0010, 0012).
MANAGE_EVENTS = (Role.DEPARTMENT_HEAD, Role.ADMIN)
HORIZON_DAYS = 365
# So lange nach dem Termin sieht das Team noch die Teilnehmerliste.
PARTICIPANTS_DAYS_AFTER = 14
AGENDA_DAYS = 42
# „Meine Stunden“ zeigt so weit zurück, wie sich noch abrechnen lässt (drei Monate plus der laufende).
PAST_TEAM_DAYS = 124
ACTIVE = (ParticipationStatus.REGISTERED, ParticipationStatus.WAITLIST)


class RegistrationError(Exception):
    """Anmeldung, Abmeldung oder Rollenwechsel ist gerade nicht möglich; die Nachricht ist für die Oberfläche."""


# Sperre durch die Abrechnung: ``portal.billing`` meldet eine Prüfung an, die einen Grund liefert, wenn eine
# Teilnahme schon eingereicht ist. So kennt diese App die Abrechnung nicht.
LockCheck = Callable[["Participation"], str | None]
_locks: list[LockCheck] = []


def register_lock(check: LockCheck) -> None:
    if check not in _locks:
        _locks.append(check)


def locked_reason(participation: Participation) -> str | None:
    for check in _locks:
        reason = check(participation)
        if reason:
            return reason
    return None


def _check_unlocked(participation: Participation) -> None:
    reason = locked_reason(participation)
    if reason:
        raise RegistrationError(reason)


# Rollen


def default_role() -> ParticipantRole:
    """Die „Rolle bei Anmeldung“ (anfangs „Teilnehmer“)."""
    role = ParticipantRole.objects.filter(is_default=True).first()
    if role is None:
        role, _ = ParticipantRole.objects.get_or_create(name="Teilnehmer", defaults={"is_default": True})
    return role


def own_member(user: Any) -> Member | None:
    """Das eigene Mitgliedsprofil des Benutzers (Verknüpfung „eigenes Profil“)."""
    if not user.is_authenticated:
        return None
    link = MemberLink.objects.filter(user=user, kind=LinkKind.SELF).select_related("member").first()
    return link.member if link else None


def member_user(member: Member) -> User | None:
    """Der eigene Benutzer eines Mitglieds, falls es einen hat."""
    link = MemberLink.objects.filter(member=member, kind=LinkKind.SELF, user__is_active=True).select_related("user")
    first = link.first()
    return first.user if first else None


def role_offered(role: ParticipantRole, event: Event) -> bool:
    """Wird die Rolle bei dieser Veranstaltungsart angeboten?"""
    if not role.is_active:
        return False
    types = [event_type.pk for event_type in role.event_types.all()]
    return not types or event.event_type_id in types


def user_may_take(user: User | None, role: ParticipantRole) -> bool:
    """Darf ein Benutzer mit seinen Benutzerrollen diese Rolle übernehmen? Ohne Einschränkung: jedes Mitglied."""
    if not role.user_roles:
        return True
    return user is not None and user.has_role(*role.user_roles)


def can_take_role(member: Member, role: ParticipantRole, event: Event) -> bool:
    return role_offered(role, event) and user_may_take(member_user(member) if role.user_roles else None, role)


def team_roles(event: Event | None = None) -> list[ParticipantRole]:
    roles = ParticipantRole.objects.filter(is_team=True, is_active=True).prefetch_related("event_types")
    return [role for role in roles if event is None or role_offered(role, event)]


def team_candidates(event: Event | None = None) -> list[Member]:
    """Mitglieder, die mindestens eine Team-Rolle (dieser Veranstaltung) übernehmen dürfen."""
    roles = team_roles(event)
    links = MemberLink.objects.filter(kind=LinkKind.SELF, user__is_active=True).select_related("member", "user")
    members_ = [
        link.member for link in links if link.member.is_active and any(user_may_take(link.user, role) for role in roles)
    ]
    return sorted(members_, key=lambda member: (member.first_name, member.last_name))


def users_without_member(role_values: Iterable[str]) -> list[User]:
    """Benutzer mit einer dieser Benutzerrollen, aber ohne eigenes Mitgliedsprofil (können kein Team sein)."""
    with_member = set(MemberLink.objects.filter(kind=LinkKind.SELF).values_list("user_id", flat=True))
    values = list(role_values)
    return [
        user
        for user in User.objects.filter(is_active=True).order_by("first_name", "email")
        if user.pk not in with_member and values and user.has_role(*values)
    ]


# Rechte


def can_manage_events(user: Any) -> bool:
    return bool(user.is_authenticated and user.has_role(*MANAGE_EVENTS))


def can_join_team(user: Any) -> bool:
    """Hat der Benutzer ein eigenes Mitgliedsprofil und darf irgendeine Team-Rolle übernehmen?"""
    if not user.is_authenticated or own_member(user) is None:
        return False
    return any(user_may_take(user, role) for role in team_roles())


def can_plan_staff(user: Any) -> bool:
    """Veranstaltungen ansehen und Teams planen: Abteilungsleitung und alle, die Team sein können."""
    return can_manage_events(user) or can_join_team(user)


def team_participation(user: Any, occurrence: Occurrence) -> Participation | None:
    member = own_member(user)
    if member is None:
        return None
    return (
        occurrence.participations.filter(member=member, role__is_team=True, status__in=ACTIVE)
        .select_related("role")
        .first()
    )


def can_lead(user: Any, occurrence: Occurrence) -> bool:
    """Termin absagen, Hinweis und Team ändern, Ausnahmen eintragen: Abteilungsleitung und Team des Termins."""
    return can_manage_events(user) or team_participation(user, occurrence) is not None


def can_see_participants(user: Any, occurrence: Occurrence, now: datetime | None = None) -> bool:
    """Teilnehmerliste mit Notfallkontakt: Abteilungsleitung; das Team bis 14 Tage nach dem Termin."""
    if can_manage_events(user):
        return True
    now = now or timezone.now()
    return can_lead(user, occurrence) and now <= occurrence.ends_at + timedelta(days=PARTICIPANTS_DAYS_AFTER)


# Zielgruppen


class Match(IntEnum):
    NO = 0
    MAYBE = 1  # passt, sobald das Gewicht eingetragen ist
    YES = 2


def age_in_year(member: Member | Guest, on: date) -> int:
    """Alter nach Jahrgang, wie bei Judo-Altersklassen (U11, U13 …)."""
    return on.year - member.birth_date.year


def match_group(
    group: TargetGroup,
    member: Member | Guest,
    on: date,
    interest_ids: set[int] | None = None,
) -> Match:
    """Passt ein Mitglied (oder ein Gast) zur Zielgruppe? Bei Gästen zählen Interessen nicht."""
    age = age_in_year(member, on)
    if group.min_age is not None and age < group.min_age:
        return Match.NO
    if group.max_age is not None and age > group.max_age:
        return Match.NO
    if group.genders and member.gender not in group.genders:
        return Match.NO
    rank = grade_rank(member.grade)
    if group.min_grade and rank < grade_rank(group.min_grade):
        return Match.NO
    if group.max_grade and rank > grade_rank(group.max_grade):
        return Match.NO
    group_interests = {interest.pk for interest in group.interests.all()}
    if group_interests and not isinstance(member, Guest):
        if interest_ids is None:
            interest_ids = {interest.pk for interest in member.interests.all()}
        if not group_interests & interest_ids:
            return Match.NO
    if group.min_weight is not None or group.max_weight is not None:
        if member.weight is None:
            return Match.MAYBE
        if group.min_weight is not None and member.weight < group.min_weight:
            return Match.NO
        if group.max_weight is not None and member.weight > group.max_weight:
            return Match.NO
    return Match.YES


def match_event(event: Event, member: Member | Guest, on: date, interest_ids: set[int] | None = None) -> Match:
    """Ohne Zielgruppe passt jeder; sonst das beste Ergebnis über alle Zielgruppen (ODER)."""
    groups = list(event.target_groups.all())
    if not groups:
        return Match.YES
    return max(match_group(group, member, on, interest_ids) for group in groups)


def matching_members(group: TargetGroup, on: date | None = None) -> list[tuple[Member, Match]]:
    on = on or timezone.localdate()
    result: list[tuple[Member, Match]] = []
    for member in Member.objects.prefetch_related("interests"):
        if not member.is_active:
            continue
        match = match_group(group, member, on)
        if match != Match.NO:
            result.append((member, match))
    return result


# Termine aus Zeitplänen


def _aware(day: date, at: time) -> datetime:
    return timezone.make_aware(datetime.combine(day, at))


def apply_schedule_team(occurrence: Occurrence) -> None:
    """Das Standard-Team des Zeitplans in einen Termin übernehmen (bestehende Teilnahmen bleiben)."""
    if occurrence.schedule_id is None:
        return
    for entry in ScheduleTeam.objects.filter(schedule_id=occurrence.schedule_id).select_related("role"):
        Participation.objects.get_or_create(
            occurrence=occurrence,
            member_id=entry.member_id,
            defaults={"role": entry.role, "status": ParticipationStatus.REGISTERED},
        )


@transaction.atomic
def generate(schedule: Schedule, today: date | None = None) -> int:
    """Erzeugt fehlende Termine eines Zeitplans bis zum Gültigkeitsende, höchstens 12 Monate im Voraus."""
    today = today or timezone.localdate()
    start = max(schedule.valid_from, today)
    end = today + timedelta(days=HORIZON_DAYS)
    if schedule.valid_until:
        end = min(end, schedule.valid_until)
    existing = {timezone.localdate(starts) for starts in schedule.occurrences.values_list("starts_at", flat=True)}
    created = 0
    day = start + timedelta(days=(schedule.weekday - start.weekday()) % 7)
    while day <= end:
        if day not in existing:
            occurrence = Occurrence(
                event=schedule.event,
                schedule=schedule,
                starts_at=_aware(day, schedule.start_time),
                ends_at=_aware(day, schedule.end_time),
            )
            occurrence.apply_rule(schedule)
            occurrence.save()
            apply_schedule_team(occurrence)
            created += 1
        day += timedelta(days=7)
    schedule.generated_until = end
    schedule.save(update_fields=["generated_until"])
    return created


def ensure_generated(today: date | None = None) -> None:
    """Rollierender Horizont: Zeitpläne, deren Termine weniger als 11 Monate reichen, werden ergänzt."""
    today = today or timezone.localdate()
    due = today + timedelta(days=HORIZON_DAYS - 30)
    for schedule in Schedule.objects.filter(Q(generated_until__isnull=True) | Q(generated_until__lt=due)).filter(
        Q(valid_until__isnull=True) | Q(valid_until__gt=timezone.localdate() - timedelta(days=1))
    ):
        if schedule.generated_until and schedule.valid_until and schedule.generated_until >= schedule.valid_until:
            continue
        generate(schedule, today)


def _replaceable(occurrences: QuerySet[Occurrence]) -> QuerySet[Occurrence]:
    """Zukünftige Termine ohne Anmeldungen, Abweichungen oder Absage – die darf das Portal neu erzeugen."""
    return (
        occurrences.filter(starts_at__gte=timezone.now(), is_modified=False, cancelled_at__isnull=True)
        .exclude(participations__status__in=ACTIVE, participations__role__is_team=False)
        .exclude(participations__confirmed_at__isnull=False)
    )


@transaction.atomic
def regenerate(schedule: Schedule) -> list[Occurrence]:
    """Nach einer Änderung am Zeitplan: zukünftige Termine neu erzeugen.

    Gibt die zukünftigen Termine zurück, die bleiben mussten (Anmeldungen, Abweichungen) und nicht mehr zum
    Zeitplan passen; über sie entscheidet die Abteilungsleitung.
    """
    _replaceable(schedule.occurrences.all()).delete()
    generate(schedule)
    for occurrence in schedule.occurrences.filter(starts_at__gte=timezone.now(), is_modified=False):
        occurrence.apply_rule(schedule)
        occurrence.save(update_fields=["registration_opens_at", "registration_closes_at"])
    return [
        occurrence
        for occurrence in schedule.occurrences.filter(starts_at__gte=timezone.now())
        if not _fits(schedule, occurrence)
    ]


def _fits(schedule: Schedule, occurrence: Occurrence) -> bool:
    starts = timezone.localtime(occurrence.starts_at)
    in_range = schedule.valid_from <= starts.date() and (
        not schedule.valid_until or starts.date() <= schedule.valid_until
    )
    return in_range and starts.weekday() == schedule.weekday and starts.time() == schedule.start_time


@transaction.atomic
def delete_schedule(schedule: Schedule) -> int:
    """Zeitplan löschen: zukünftige Termine ohne Anmeldungen fallen weg, die übrigen bleiben als Einzeltermine."""
    _replaceable(schedule.occurrences.all()).delete()
    kept = schedule.occurrences.filter(starts_at__gte=timezone.now()).count()
    schedule.delete()
    return kept


@transaction.atomic
def update_occurrence(occurrence: Occurrence, fields: Iterable[str], by: User | None = None) -> None:
    """Abweichung an einem einzelnen Termin (Uhrzeit, Ort, Anmeldezeitraum) – der Termin bleibt dann bei Neuerzeugung.

    Ändern sich Uhrzeit oder Ort, bekommen Angemeldete und Team eine Benachrichtigung.
    """
    changed = set(fields)
    moved = bool(changed & {"starts_at", "ends_at", "location"})
    if moved or changed & {"registration_opens_at", "registration_closes_at"}:
        occurrence.is_modified = True
    occurrence.save()
    if moved:
        notices.changed(occurrence, by)


# Absage


@transaction.atomic
def cancel(occurrence: Occurrence, by: User | None = None) -> None:
    if occurrence.is_cancelled:
        return
    occurrence.cancelled_at = timezone.now()
    occurrence.save(update_fields=["cancelled_at"])
    log.info("Termin %s abgesagt", occurrence.pk)
    notices.cancelled(occurrence, by)


def cancel_range(event: Event, first: date, last: date, by: User | None = None) -> int:
    """Alle Termine einer Veranstaltung von–bis absagen (Ferien, Hallensperrung)."""
    occurrences = event.occurrences.filter(
        cancelled_at__isnull=True,
        starts_at__gte=_aware(first, time.min),
        starts_at__lte=_aware(last, time.max),
    )
    count = 0
    for occurrence in occurrences:
        cancel(occurrence, by)
        count += 1
    return count


def uncancel(occurrence: Occurrence) -> None:
    occurrence.cancelled_at = None
    occurrence.save(update_fields=["cancelled_at"])


# Anmeldung


def window(occurrence: Occurrence, now: datetime | None = None) -> str:
    """„before“ (noch nicht offen), „open“ oder „closed“."""
    now = now or timezone.now()
    opens = occurrence.registration_opens
    if opens and now < opens:
        return "before"
    if now >= occurrence.registration_closes:
        return "closed"
    return "open"


def registered_count(occurrence: Occurrence) -> int:
    """Belegte Plätze: angemeldete Teilnahmen ohne Team-Rollen."""
    return occurrence.participations.filter(status=ParticipationStatus.REGISTERED, role__is_team=False).count()


def check_register(occurrence: Occurrence, member: Member, match: Match | None = None) -> None:
    """Prüft, ob sich das Mitglied selbst (bzw. über die Eltern) anmelden kann."""
    if occurrence.is_cancelled:
        raise RegistrationError("Der Termin ist abgesagt.")
    _check_not_team(occurrence, member)
    state = window(occurrence)
    if state == "before":
        opens = timezone.localtime(occurrence.registration_opens)
        raise RegistrationError(f"Die Anmeldung öffnet am {opens:%d.%m.%Y um %H:%M} Uhr.")
    if state == "closed":
        raise RegistrationError("Die Anmeldung ist geschlossen.")
    if match is None:
        match = match_event(occurrence.event, member, timezone.localdate(occurrence.starts_at))
    if match == Match.NO:
        raise RegistrationError(f"{occurrence.event.title} passt nicht zu {member.first_name}.")


def _check_not_team(occurrence: Occurrence, member: Member) -> None:
    team = occurrence.participations.filter(member=member, role__is_team=True, status__in=ACTIVE).first()
    if team:
        raise RegistrationError(f"{member.first_name} ist als {team.role.name} eingetragen.")


@transaction.atomic
def register(
    occurrence: Occurrence,
    member: Member,
    by: User,
    *,
    weight: Decimal | None = None,
    note: str = "",
    exception: bool = False,
) -> Participation:
    """Meldet ein Mitglied mit der „Rolle bei Anmeldung“ an. Ausnahmen (Abteilungsleitung, Team) gelten unabhängig
    von Zielgruppe, Anmeldezeitraum und Höchstzahl. Ist der Termin voll, kommt das Mitglied auf die Warteliste."""
    if exception:
        if occurrence.is_cancelled:
            raise RegistrationError("Der Termin ist abgesagt.")
        _check_not_team(occurrence, member)
    else:
        check_register(occurrence, member)
    existing = Participation.objects.filter(occurrence=occurrence, member=member).first()
    if existing and existing.is_active and not exception:
        return existing
    if weight is not None and weight != member.weight:
        member.weight = weight
        member.save(update_fields=["weight", "updated_at"])
    if occurrence.event.weight_required and weight is None:
        weight = member.weight
    capacity = occurrence.event.capacity
    full = capacity is not None and registered_count(occurrence) >= capacity
    status = ParticipationStatus.WAITLIST if full and not exception else ParticipationStatus.REGISTERED
    participation, _ = Participation.objects.update_or_create(
        occurrence=occurrence,
        member=member,
        defaults={
            "role": default_role(),
            "status": status,
            "registered_by": by,
            "exception_by": by if exception else None,
            "weight": weight,
            "note": note,
            "created_at": timezone.now(),
        },
    )
    log.info("Mitglied %s für Termin %s: %s", member.pk, occurrence.pk, status)
    return participation


@transaction.atomic
def unregister(participation: Participation, by: User, *, force: bool = False) -> None:
    """Abmelden bis zum Anmeldeschluss; danach nur Abteilungsleitung und Team (``force``)."""
    if not force and window(participation.occurrence) == "closed":
        raise RegistrationError(
            "Nach dem Anmeldeschluss kannst du dich nicht mehr abmelden. Sag bitte dem Trainer Bescheid."
        )
    was_registered = participation.status == ParticipationStatus.REGISTERED
    participation.status = ParticipationStatus.CANCELLED
    participation.registered_by = by
    participation.save(update_fields=["status", "registered_by", "updated_at"])
    if was_registered:
        promote(participation.occurrence)


def promote(occurrence: Occurrence) -> list[Participation]:
    """Rückt von der Warteliste nach, solange Plätze frei sind, und benachrichtigt (Push, sonst Mail)."""
    capacity = occurrence.event.capacity
    promoted: list[Participation] = []
    if capacity is None:
        return promoted
    free = capacity - registered_count(occurrence)
    waiting = occurrence.participations.filter(status=ParticipationStatus.WAITLIST).select_related("member", "guest")
    for participation in waiting[: max(free, 0)]:
        participation.status = ParticipationStatus.REGISTERED
        participation.save(update_fields=["status", "updated_at"])
        promoted.append(participation)
        notices.promoted(participation)
    return promoted


# Team


@transaction.atomic
def set_team(occurrence: Occurrence, member: Member, role: ParticipantRole, by: User | None = None) -> Participation:
    """Mitglied mit einer Team-Rolle eintragen oder die Rolle wechseln. War es als Teilnehmer angemeldet, wird die
    Teilnahme umgestellt; ein frei gewordener Platz geht an die Warteliste."""
    if not role.is_team:
        raise RegistrationError(f"{role.name} ist keine Team-Rolle.")
    if not can_take_role(member, role, occurrence.event):
        raise RegistrationError(f"{member.first_name} kann bei {occurrence.event.title} nicht {role.name} sein.")
    existing = Participation.objects.filter(occurrence=occurrence, member=member).select_related("role").first()
    if existing and existing.is_confirmed:
        raise RegistrationError("Bestätigte Stunden bleiben für die Abrechnung, wie sie sind.")
    if existing:
        _check_unlocked(existing)
    freed = existing is not None and not existing.role.is_team and existing.status == ParticipationStatus.REGISTERED
    participation, _ = Participation.objects.update_or_create(
        occurrence=occurrence,
        member=member,
        defaults={
            "role": role,
            "status": ParticipationStatus.REGISTERED,
            "registered_by": by,
            "exception_by": None,
            "weight": None,
        },
    )
    if freed:
        promote(occurrence)
    return participation


def remove_team(participation: Participation) -> None:
    if participation.is_confirmed:
        raise RegistrationError("Bestätigte Stunden bleiben für die Abrechnung erhalten.")
    participation.delete()


def confirm(participation: Participation, minutes: int | None = None) -> None:
    """Nach dem Termin: „durchgeführt, ich war als Trainer/Co-Trainer da“ – die Stunden für die Abrechnung.

    Bestätigte Stunden lassen sich so auch korrigieren, bis der Monat zur Abrechnung eingereicht ist.
    """
    _check_unlocked(participation)
    if not participation.role.is_billable:
        raise RegistrationError(f"Für {participation.role.name} werden keine Stunden bestätigt.")
    if participation.occurrence.starts_at > timezone.now():
        raise RegistrationError("Bestätigen kannst du erst, wenn der Termin begonnen hat.")
    if participation.occurrence.is_cancelled:
        raise RegistrationError("Der Termin ist abgesagt.")
    participation.confirmed_at = participation.confirmed_at or timezone.now()
    participation.minutes = minutes or participation.occurrence.minutes
    participation.save(update_fields=["confirmed_at", "minutes", "updated_at"])


@transaction.atomic
def create_event(
    event: Event,
    *,
    dates: str,
    once: dict[str, Any] | None = None,
    weekly: dict[str, Any] | None = None,
    team: tuple[Member, ParticipantRole] | None = None,
) -> list[Occurrence]:
    """Veranstaltung mit ihren Terminen in einem Schritt anlegen (ADR 0012).

    ``dates``: „once“ (ein Termin, Team am Termin), „weekly“ (je Wochentag ein Zeitplan mit Standard-Team) oder
    „later“ (nur die Veranstaltung). ``event`` ist gespeichert; schlägt etwas fehl, wird alles zurückgerollt.
    """
    if team and not can_take_role(team[0], team[1], event):
        raise RegistrationError(f"{team[0].first_name} kann bei {event.title} nicht {team[1].name} sein.")
    if dates == "once" and once:
        occurrence = Occurrence.objects.create(event=event, **once)
        if team:
            set_team(occurrence, *team)
        return [occurrence]
    if dates == "weekly" and weekly:
        rule = dict(weekly)
        weekdays = rule.pop("weekdays")
        for weekday in sorted(weekdays):
            schedule = Schedule.objects.create(event=event, weekday=weekday, **rule)
            if team:
                ScheduleTeam.objects.create(schedule=schedule, member=team[0], role=team[1])
            generate(schedule)
        return list(event.occurrences.all())
    return []


def _future(schedule: Schedule) -> QuerySet[Occurrence]:
    return schedule.occurrences.filter(starts_at__gte=timezone.now(), cancelled_at__isnull=True)


@transaction.atomic
def set_schedule_team(schedule: Schedule, member: Member, role: ParticipantRole) -> None:
    """Standard-Team eines Zeitplans ändern; zukünftige Termine ziehen nach (bestätigte Stunden bleiben)."""
    if not role.is_team or not can_take_role(member, role, schedule.event):
        raise RegistrationError(f"{member.first_name} kann bei {schedule.event.title} nicht {role.name} sein.")
    ScheduleTeam.objects.update_or_create(schedule=schedule, member=member, defaults={"role": role})
    for occurrence in _future(schedule):
        existing = Participation.objects.filter(occurrence=occurrence, member=member).select_related("role").first()
        if existing is None:
            Participation.objects.create(
                occurrence=occurrence, member=member, role=role, status=ParticipationStatus.REGISTERED
            )
        elif existing.role.is_team and not existing.is_confirmed and existing.role_id != role.pk:
            existing.role = role
            existing.save(update_fields=["role", "updated_at"])


@transaction.atomic
def remove_schedule_team(entry: ScheduleTeam) -> None:
    """Aus dem Standard-Team nehmen; zukünftige, unbestätigte Team-Teilnahmen fallen weg."""
    Participation.objects.filter(
        occurrence__in=_future(entry.schedule), member=entry.member, role__is_team=True, confirmed_at=None
    ).delete()
    entry.delete()


# Ansichten


@dataclass
class AgendaItem:
    occurrence: Occurrence
    match: Match
    participation: Participation | None = None
    window: str = "open"

    @property
    def team_role(self) -> ParticipantRole | None:
        """Team-Rolle des Mitglieds an diesem Termin (Trainer …), sonst None."""
        p = self.participation
        return p.role if p and p.is_active and p.role.is_team else None

    @property
    def status(self) -> str:
        if self.team_role:
            return "team"
        if self.participation and self.participation.is_active:
            return self.participation.status
        return "cancelled" if self.participation else ""

    @property
    def can_register(self) -> bool:
        active = self.participation is not None and self.participation.is_active
        return not active and not self.occurrence.is_cancelled and self.window == "open" and self.match != Match.NO

    @property
    def can_unregister(self) -> bool:
        active = self.participation is not None and self.participation.is_active and not self.team_role
        return active and self.window != "closed" and not self.occurrence.is_cancelled

    @property
    def quick(self) -> bool:
        """Anmelden mit einem Klick: ohne Pflichtgewicht. Sonst über das Formular."""
        return not self.occurrence.event.weight_required


@dataclass
class AgendaRow:
    """Ein eigenes Mitglied an einem Termin."""

    link: MemberLink
    item: AgendaItem

    @property
    def member(self) -> Member:
        return self.link.member


@dataclass
class AgendaEntry:
    """Ein Termin mit den eigenen Mitgliedern, für die er passt oder die eingetragen sind – jeder Termin nur einmal."""

    occurrence: Occurrence
    rows: list[AgendaRow] = field(default_factory=list)


@dataclass
class Agenda:
    entries: list[AgendaEntry] = field(default_factory=list)
    others: list[Occurrence] = field(default_factory=list)  # passen zu keinem eigenen Mitglied
    several: bool = False  # mehrere eigene Mitglieder: Namen an jeder Zeile


def upcoming(days: int = AGENDA_DAYS) -> QuerySet[Occurrence]:
    now = timezone.now()
    return (
        Occurrence.objects.filter(ends_at__gte=now, starts_at__lte=now + timedelta(days=days))
        .select_related("event")
        .prefetch_related("event__target_groups__interests", "participations__role", "participations__member")
    )


def agenda(user: Any, days: int = AGENDA_DAYS) -> Agenda | None:
    """Die nächsten Termine nach Datum, jeder einmal; darunter die eigenen Mitglieder mit Status und Knopf.

    Ohne eigene Mitglieder: ``None``.
    """
    links = members.effective_links(user)
    if not links:
        return None
    ensure_generated()
    occurrences = list(upcoming(days))
    member_ids = [link.member.pk for link in links]
    participations = {
        (p.occurrence_id, p.member_id): p
        for p in Participation.objects.filter(member_id__in=member_ids, occurrence__in=occurrences).select_related(
            "role"
        )
    }
    interests = {link.member.pk: {interest.pk for interest in link.member.interests.all()} for link in links}
    result = Agenda(several=len(links) > 1)
    for occurrence in occurrences:
        on = timezone.localdate(occurrence.starts_at)
        state = window(occurrence)
        entry = AgendaEntry(occurrence)
        for link in links:
            member = link.member
            match = match_event(occurrence.event, member, on, interests[member.pk])
            participation = participations.get((occurrence.pk, member.pk))
            if match != Match.NO or (participation and participation.is_active):
                entry.rows.append(AgendaRow(link, AgendaItem(occurrence, match, participation, state)))
        if entry.rows:
            result.entries.append(entry)
        else:
            result.others.append(occurrence)
    return result


def next_entries(user: Any, count: int = 3) -> list[AgendaEntry]:
    """Für die Startseite: die nächsten Termine, die zu einem eigenen Mitglied passen – jeder nur einmal."""
    result = agenda(user, days=21)
    if result is None:
        return []
    return [entry for entry in result.entries if not entry.occurrence.is_cancelled][:count]


@dataclass
class Participant:
    participation: Participation
    age: int
    weight: Decimal | None
    guardians: list[User]

    @property
    def member(self) -> Member | None:
        return self.participation.member

    @property
    def guest(self) -> Guest | None:
        return self.participation.guest

    @property
    def person(self) -> Member | Guest:
        return self.participation.person


def participants(occurrence: Occurrence) -> list[Participant]:
    """Teilnehmerliste (ohne Team) mit Judo-Daten und Notfallkontakt (Telefon des Mitglieds, Eltern; bei Gästen
    Telefon und Erziehungsberechtigte)."""
    on = timezone.localdate(occurrence.starts_at)
    rows = occurrence.participations.filter(status__in=ACTIVE, role__is_team=False).select_related(
        "member", "guest", "exception_by", "role"
    )
    return [
        Participant(
            participation=participation,
            age=age_in_year(participation.person, on),
            weight=participation.weight or participation.person.weight,
            guardians=members.guardians(participation.member) if participation.member else [],
        )
        for participation in rows
    ]


def team(occurrence: Occurrence) -> list[Participation]:
    return list(
        occurrence.participations.filter(status__in=ACTIVE, role__is_team=True)
        .select_related("member", "role")
        .order_by("role__order", "member__first_name")
    )


def own_team(user: User) -> tuple[list[Participation], list[Participation]]:
    """„Meine Stunden“: kommende Termine mit eigener Team-Rolle und die letzten vier Monate (wie die Abrechnung)."""
    member = own_member(user)
    if member is None:
        return [], []
    now = timezone.now()
    rows = Participation.objects.filter(member=member, role__is_team=True, status__in=ACTIVE).select_related(
        "occurrence__event", "role"
    )
    coming = list(rows.filter(occurrence__ends_at__gte=now).order_by("occurrence__starts_at")[:50])
    past = list(
        rows.filter(
            occurrence__ends_at__lt=now, occurrence__starts_at__gte=now - timedelta(days=PAST_TEAM_DAYS)
        ).order_by("-occurrence__starts_at")
    )
    return coming, past


# Empfänger


def participant_users(occurrence: Occurrence) -> set[User]:
    """Benutzer aller aktiven Teilnahmen inkl. Team (das Mitglied selbst, Eltern bis 18)."""
    users: set[User] = set()
    rows = occurrence.participations.filter(status__in=ACTIVE, member__isnull=False).select_related("member")
    for participation in rows:
        users.update(members.member_users(participation.member))  # type: ignore[arg-type]
    return users


def participant_guests(occurrence: Occurrence) -> list[Guest]:
    return [p.guest for p in occurrence.participations.filter(status__in=ACTIVE).select_related("guest") if p.guest]
