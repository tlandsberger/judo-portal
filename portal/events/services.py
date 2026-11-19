"""Fachlogik der Veranstaltungen: Zielgruppen, Termine aus Zeitplänen, Teilnahme mit Rollen und Warteliste, Rechte.

Auf Mitglieder greift das Modul nur über ``portal.members.services`` zu (eigene Mitglieder, Eltern).
"""

from __future__ import annotations

import calendar
import logging
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import IntEnum
from typing import Any

from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import formats, timezone

from portal.accounts.models import Role, User
from portal.core import audit
from portal.members import services as members
from portal.members.models import LinkKind, Member, MemberLink, grade_rank

from . import closures, notices
from .models import (
    Criteria,
    Event,
    Guest,
    Occurrence,
    OccurrenceTargetGroup,
    ParticipantRole,
    Participation,
    ParticipationStatus,
    Repeat,
    Schedule,
    ScheduleTeam,
    TargetGroupTemplate,
    TargetMode,
)

log = logging.getLogger(__name__)

# Veranstaltungen, Zeitpläne, Zielgruppen, Arten und Rollen pflegt die Abteilungsleitung (ADR 0010, 0012).
MANAGE_EVENTS = (Role.DEPARTMENT_HEAD, Role.ADMIN)
HORIZON_DAYS = 365
# So lange nach dem Termin sieht das Team noch die Teilnehmerliste.
PARTICIPANTS_DAYS_AFTER = 14
# So lange vor dem Termin erinnert das Portal die Abteilungsleitung, wenn noch kein Trainer eingeteilt ist.
TRAINER_MISSING_REMIND = timedelta(days=2)
ACTIVE = (ParticipationStatus.REGISTERED, ParticipationStatus.WAITLIST)


class RegistrationError(Exception):
    """Anmeldung, Abmeldung oder Rollenwechsel ist gerade nicht möglich; die Nachricht ist für die Oberfläche."""


# Sperre durch die Abrechnung: ``portal.billing`` meldet eine Prüfung an, die einen Grund liefert, wenn eine
# Teilnahme schon eingereicht ist. So kennt diese App die Abrechnung nicht.
LockCheck = Callable[["Participation"], str | None]
_locks: list[LockCheck] = []
# Weitere Voraussetzungen für eine Rolle aus anderen Apps (z. B. Stundensatz aus ``billing``): Grund oder ``None``.
RoleCheck = Callable[[Member, "ParticipantRole", date], str | None]
_role_checks: list[RoleCheck] = []


def _when(occurrence: Occurrence) -> str:
    return f"{occurrence.event.title} am {timezone.localtime(occurrence.starts_at):%d.%m.%Y %H:%M}"


def _audit(by: Any, action: str, summary: str, participation: Participation | None = None, **changes: Any) -> None:
    """Protokolleintrag für Termine (ADR 0015); Bezug ist das Mitglied bzw. der Gast der Teilnahme."""
    audit.log(
        by,
        audit.Area.EVENTS,
        action,
        summary,
        member=participation.member_id if participation else None,
        guest=participation.guest_id if participation else None,
        changes=changes or None,
    )


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


def register_role_check(check: RoleCheck) -> None:
    if check not in _role_checks:
        _role_checks.append(check)


def role_unavailable(member: Member, role: ParticipantRole, event: Event, day: date | None = None) -> str | None:
    """Warum das Mitglied die Rolle bei dieser Veranstaltung (am Tag ``day``, sonst heute) nicht übernehmen kann."""
    if not role_offered(role, event) or not user_may_take(member_user(member) if role.user_roles else None, role):
        return f"{member.first_name} kann bei {event.title} nicht {role.name} sein."
    for check in _role_checks:
        reason = check(member, role, day or timezone.localdate())
        if reason:
            return reason
    return None


def can_take_role(member: Member, role: ParticipantRole, event: Event, day: date | None = None) -> bool:
    return role_unavailable(member, role, event, day) is None


def _check_role(member: Member, role: ParticipantRole, event: Event, day: date | None = None) -> None:
    reason = role_unavailable(member, role, event, day)
    if reason:
        raise RegistrationError(reason)


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


def can_add_occurrence(user: Any, event: Event, today: date | None = None) -> bool:
    """Neue Termine anlegen: Abteilungsleitung; Übungsleiter nur bei Veranstaltungen, in deren laufendem Zeitplan sie
    fest eingeteilt sind."""
    if can_manage_events(user):
        return True
    member = own_member(user) if user.is_authenticated else None
    if member is None or not can_join_team(user):
        return False
    today = today or timezone.localdate()
    return ScheduleTeam.objects.filter(
        Q(schedule__valid_until__isnull=True) | Q(schedule__valid_until__gte=today),
        schedule__event=event,
        member=member,
    ).exists()


def add_occurrence(occurrence: Occurrence, by: User | None = None) -> Occurrence:
    """Einzelnen Termin zu einer Veranstaltung anlegen (ohne Zeitplan) und protokollieren."""
    occurrence.save()
    _audit(by, "occurrence_create", f"Termin {_when(occurrence)} angelegt")
    return occurrence


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
    group: Criteria,
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


def target_groups(occurrence: Occurrence) -> list[Criteria]:
    """Zielgruppen eines Termins: eigene, wenn sie abweichen, sonst die der Veranstaltung (ADR 0019)."""
    if occurrence.custom_target_groups:
        return list(occurrence.target_groups.all())
    return list(occurrence.event.target_groups.all())


def match_occurrence(occurrence: Occurrence, person: Member | Guest, interest_ids: set[int] | None = None) -> Match:
    """Wie ``match_event``, aber mit den Zielgruppen des Termins."""
    groups = target_groups(occurrence)
    if not groups:
        return Match.YES
    on = timezone.localdate(occurrence.starts_at)
    return max(match_group(group, person, on, interest_ids) for group in groups)


def is_recommendation(occurrence: Occurrence) -> bool:
    """Zielgruppen nur als Empfehlung: Wer nicht passt, darf sich trotzdem anmelden."""
    return occurrence.event.target_mode == TargetMode.RECOMMENDED


def not_in_group_message(member: Member | Guest, own: bool) -> str:
    """Hinweis, wenn die Zielgruppe Vorgabe ist und nicht passt; ``own`` heißt: das eigene Mitgliedsprofil."""
    who = "Du gehörst" if own else f"{member.first_name} gehört"
    return (
        f"{who} leider nicht zur Zielgruppe dieses Termins. Anmeldung nur durch Übungs- oder Abteilungsleiter möglich."
    )


@transaction.atomic
def customize_target_groups(occurrence: Occurrence, by: User | None = None) -> None:
    """Der Termin bekommt eigene Zielgruppen, zunächst als Kopie der Zielgruppen der Veranstaltung."""
    if occurrence.custom_target_groups:
        return
    for group in occurrence.event.target_groups.all():
        copy = OccurrenceTargetGroup.objects.create(
            occurrence=occurrence, name=group.name, **{name: getattr(group, name) for name in group.CRITERIA}
        )
        copy.interests.set(group.interests.all())
    occurrence.custom_target_groups = True
    occurrence.is_modified = True  # bleibt bei Neuerzeugung aus dem Zeitplan erhalten
    occurrence.save(update_fields=["custom_target_groups", "is_modified"])
    audit.log(by, audit.Area.EVENTS, "occurrence_target_groups", f"Zielgruppen für {_when(occurrence)} angepasst")


@transaction.atomic
def save_occurrence_target_groups(occurrence: Occurrence, formset: Any, by: User | None = None) -> None:
    formset.save()
    groups = "; ".join(str(group) for group in occurrence.target_groups.all()) or "alle"
    audit.log(by, audit.Area.EVENTS, "occurrence_target_groups", f"Zielgruppen für {_when(occurrence)}: {groups}")


@transaction.atomic
def reset_target_groups(occurrence: Occurrence, by: User | None = None) -> None:
    """Wieder die Zielgruppen der Veranstaltung."""
    occurrence.target_groups.all().delete()
    occurrence.custom_target_groups = False
    occurrence.save(update_fields=["custom_target_groups"])
    audit.log(
        by,
        audit.Area.EVENTS,
        "occurrence_target_groups",
        f"Zielgruppen für {_when(occurrence)} wieder wie die Veranstaltung",
    )


def matching_members(target: Criteria | Event, on: date | None = None) -> list[tuple[Member, Match]]:
    """Aktive Mitglieder, die zu einer Vorlage oder Veranstaltung passen (auch „vielleicht“)."""
    on = on or timezone.localdate()
    result: list[tuple[Member, Match]] = []
    for member in Member.objects.prefetch_related("interests"):
        if not member.is_active:
            continue
        match = match_event(target, member, on) if isinstance(target, Event) else match_group(target, member, on)
        if match != Match.NO:
            result.append((member, match))
    return result


def save_target_groups(formset: Any) -> list[TargetGroupTemplate]:
    """Zielgruppen einer Veranstaltung speichern; angehakte zusätzlich als Vorlage anlegen (Kopie)."""
    formset.save()
    templates = []
    for form in formset.forms:
        data = getattr(form, "cleaned_data", {})
        if not data.get("save_as_template") or data.get("DELETE") or form.instance.pk is None:
            continue
        group = form.instance
        template = TargetGroupTemplate.objects.create(
            name=group.name.strip(), **{name: getattr(group, name) for name in group.CRITERIA}
        )
        template.interests.set(group.interests.all())
        templates.append(template)
    return templates


def template_data() -> dict[str, dict[str, Any]]:
    """Vorlagen für die Übernahme im Formular (als JSON ins Template)."""
    data: dict[str, dict[str, Any]] = {}
    for template in TargetGroupTemplate.objects.prefetch_related("interests"):
        values: dict[str, Any] = {name: getattr(template, name) for name in template.CRITERIA}
        for name in ("min_weight", "max_weight"):
            if values[name] is not None:
                values[name] = formats.number_format(values[name], 1)
        values["name"] = template.name
        values["interests"] = [interest.pk for interest in template.interests.all()]
        data[str(template.pk)] = values
    return data


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


def nth_weekday(year: int, month: int, weekday: int, nth: int) -> date | None:
    """Der n-te Wochentag eines Monats (``nth=-1``: der letzte); ``None``, wenn es ihn nicht gibt."""
    if nth < 0:
        last = date(year, month, calendar.monthrange(year, month)[1])
        return last - timedelta(days=(last.weekday() - weekday) % 7)
    first = date(year, month, 1)
    day = first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (nth - 1))
    return day if day.month == month else None


def schedule_dates(schedule: Schedule, start: date, end: date) -> Iterator[date]:
    """Die Tage eines Zeitplans von ``start`` bis ``end``: alle x Wochen ab „Gültig ab“ oder der n-te im Monat."""
    if schedule.repeat == Repeat.MONTH:
        year, month = start.year, start.month
        while date(year, month, 1) <= end:
            day = nth_weekday(year, month, schedule.weekday, schedule.week_of_month or 1)
            if day and start <= day <= end:
                yield day
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        return
    anchor = schedule.valid_from + timedelta(days=(schedule.weekday - schedule.valid_from.weekday()) % 7)
    step = 7 * max(schedule.interval, 1)
    day = anchor
    if start > anchor:
        day = anchor + timedelta(days=-(-(start - anchor).days // step) * step)
    while day <= end:
        yield day
        day += timedelta(days=step)


def on_schedule(schedule: Schedule, day: date) -> bool:
    """Liegt ``day`` im Rhythmus des Zeitplans (Gültigkeit und Uhrzeit nicht geprüft)?"""
    return next(schedule_dates(schedule, day, day), None) == day


@transaction.atomic
def generate(schedule: Schedule, today: date | None = None, *, sync_closures: bool = True) -> int:
    """Erzeugt fehlende Termine eines Zeitplans bis zum Gültigkeitsende, höchstens 12 Monate im Voraus."""
    today = today or timezone.localdate()
    start = max(schedule.valid_from, today)
    end = today + timedelta(days=HORIZON_DAYS)
    if schedule.valid_until:
        end = min(end, schedule.valid_until)
    existing = {timezone.localdate(starts) for starts in schedule.occurrences.values_list("starts_at", flat=True)}
    created = 0
    for day in schedule_dates(schedule, start, end):
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
    schedule.generated_until = end
    schedule.save(update_fields=["generated_until"])
    if sync_closures and created and schedule.closures.exists():
        closures.sync([schedule])  # neue Termine in Ferien und an Feiertagen fallen gleich aus (ADR 0026)
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
def regenerate(schedule: Schedule, *, sync_closures: bool = True) -> list[Occurrence]:
    """Nach einer Änderung am Zeitplan: zukünftige Termine neu erzeugen.

    Gibt die zukünftigen Termine zurück, die bleiben mussten (Anmeldungen, Abweichungen) und nicht mehr zum
    Zeitplan passen; über sie entscheidet die Abteilungsleitung.
    """
    _replaceable(schedule.occurrences.all()).delete()
    generate(schedule, sync_closures=sync_closures)
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
    return in_range and on_schedule(schedule, starts.date()) and starts.time() == schedule.start_time


@transaction.atomic
def delete_schedule(schedule: Schedule) -> int:
    """Zeitplan löschen: zukünftige Termine ohne Anmeldungen fallen weg, die übrigen bleiben als Einzeltermine."""
    _replaceable(schedule.occurrences.all()).delete()
    kept = schedule.occurrences.filter(starts_at__gte=timezone.now()).count()
    schedule.delete()
    return kept


@transaction.atomic
def update_occurrence(occurrence: Occurrence, fields: Iterable[str], by: User | None = None) -> None:
    """Abweichung an einem einzelnen Termin (Uhrzeit, Ort, Anmeldezeitraum, ob die Übungsleiter zur Höchstzahl
    zählen) – der Termin bleibt dann bei Neuerzeugung.

    Ändern sich Uhrzeit oder Ort, bekommen Angemeldete und Team eine Benachrichtigung.
    """
    changed = set(fields)
    moved = bool(changed & {"starts_at", "ends_at", "location"})
    if moved or changed & {"registration_opens_at", "registration_closes_at", "team_counts"}:
        occurrence.is_modified = True
    occurrence.save()
    if "team_counts" in changed:
        promote(occurrence)  # zählen die Übungsleiter nicht mehr mit, werden Plätze frei
    if changed:
        labels = audit.labels_for(Occurrence, changed)
        _audit(by, "occurrence_update", f"{_when(occurrence)} geändert: {', '.join(sorted(labels.values()))}")
    if moved:
        notices.changed(occurrence, by)


# Absage


@transaction.atomic
def cancel(occurrence: Occurrence, by: User | None = None, *, notify: bool = True) -> None:
    if occurrence.is_cancelled:
        return
    occurrence.cancelled_at = timezone.now()
    occurrence.save(update_fields=["cancelled_at"])
    log.info("Termin %s abgesagt", occurrence.pk)
    _audit(by, "cancel", f"{_when(occurrence)} abgesagt{'' if notify else ' (nachträglich)'}")
    if notify:
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


def uncancel(occurrence: Occurrence, by: User | None = None) -> None:
    closures.exempt(occurrence)  # in Ferien oder an Feiertagen: bleibt trotzdem
    occurrence.cancelled_at = None
    occurrence.save(update_fields=["cancelled_at"])
    _audit(by, "uncancel", f"Absage von {_when(occurrence)} zurückgenommen")


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
    """Belegte Plätze: angemeldete Teilnehmer, dazu die Übungsleiter, wenn sie zur Höchstzahl zählen."""
    taken = occurrence.participations.filter(status=ParticipationStatus.REGISTERED)
    if not occurrence.counts_team:
        taken = taken.filter(role__is_team=False)
    return taken.count()


def _check_team_place(occurrence: Occurrence, existing: Participation | None, by: User | None) -> None:
    """Zählen die Übungsleiter zur Höchstzahl, trägt über die Höchstzahl hinaus nur die Abteilungsleitung ein
    (oder das Portal selbst, z. B. für fest eingeteilte Übungsleiter)."""
    capacity = occurrence.event.capacity
    if capacity is None or not occurrence.counts_team or by is None or can_manage_events(by):
        return
    if existing is not None and existing.status == ParticipationStatus.REGISTERED:
        return  # belegt schon einen Platz
    if registered_count(occurrence) >= capacity:
        raise RegistrationError(
            "Der Termin ist voll, und die Übungsleiter zählen zur Höchstzahl. Über die Höchstzahl hinaus trägt "
            "nur die Abteilungsleitung ein."
        )


def check_register(
    occurrence: Occurrence, member: Member, match: Match | None = None, *, by: User | None = None
) -> Match:
    """Prüft, ob sich das Mitglied selbst (bzw. über die Eltern) anmelden kann, und gibt das Matching zurück.

    Ist die Zielgruppe eine Vorgabe und passt nicht, geht die Anmeldung nur über Übungs- oder Abteilungsleiter;
    ist sie eine Empfehlung, ist die Anmeldung erlaubt (ADR 0019).
    """
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
        match = match_occurrence(occurrence, member)
    if match == Match.NO and not is_recommendation(occurrence):
        own = by is not None and member_user(member) == by
        raise RegistrationError(not_in_group_message(member, own))
    return match


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
    off_target = False
    if exception:
        if occurrence.is_cancelled:
            raise RegistrationError("Der Termin ist abgesagt.")
        _check_not_team(occurrence, member)
    else:
        off_target = check_register(occurrence, member, by=by) == Match.NO
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
            "off_target": off_target,
            "weight": weight,
            "note": note,
            "created_at": timezone.now(),
        },
    )
    log.info("Mitglied %s für Termin %s: %s", member.pk, occurrence.pk, status)
    if off_target:
        transaction.on_commit(lambda: notices.off_target(participation, by))
    state = "auf der Warteliste" if status == ParticipationStatus.WAITLIST else "angemeldet"
    _audit(
        by,
        "register",
        f"{member.display_name} für {_when(occurrence)} {state}{' (Ausnahme)' if exception else ''}",
        participation,
    )
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
    _audit(
        by,
        "unregister",
        f"{participation.person.display_name} von {_when(participation.occurrence)} abgemeldet",
        participation,
    )
    if was_registered:
        promote(participation.occurrence)


def promote(occurrence: Occurrence) -> list[Participation]:
    """Rückt von der Warteliste nach, solange Plätze frei sind, und benachrichtigt die Nachrückenden."""
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
        _audit(
            None,
            "promote",
            f"{participation.person.display_name} für {_when(occurrence)} von der Warteliste nachgerückt",
            participation,
        )
        notices.promoted(participation)
    return promoted


def promote_upcoming(event: Event) -> None:
    """Nach einer Änderung an der Veranstaltung (z. B. Übungsleiter zählen nicht mehr mit): Warteliste der kommenden
    Termine nachrücken lassen."""
    upcoming = event.occurrences.filter(starts_at__gte=timezone.now(), cancelled_at__isnull=True)
    for occurrence in upcoming.filter(participations__status=ParticipationStatus.WAITLIST).distinct():
        occurrence.event = event
        promote(occurrence)


# Team


@transaction.atomic
def set_team(occurrence: Occurrence, member: Member, role: ParticipantRole, by: User | None = None) -> Participation:
    """Mitglied mit einer Team-Rolle eintragen oder die Rolle wechseln. War es als Teilnehmer angemeldet, wird die
    Teilnahme umgestellt; ein frei gewordener Platz geht an die Warteliste."""
    if not role.is_team:
        raise RegistrationError(f"{role.name} ist keine Übungsleiter-Rolle.")
    _check_role(member, role, occurrence.event, timezone.localdate(occurrence.starts_at))
    existing = Participation.objects.filter(occurrence=occurrence, member=member).select_related("role").first()
    if existing and existing.is_confirmed:
        raise RegistrationError("Bestätigte Stunden bleiben für die Abrechnung, wie sie sind.")
    if existing:
        _check_unlocked(existing)
    _check_team_place(occurrence, existing, by)
    freed = (
        existing is not None
        and not existing.role.is_team
        and existing.status == ParticipationStatus.REGISTERED
        and not occurrence.counts_team
    )
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
    _audit(by, "team", f"{member.display_name} als {role.name} für {_when(occurrence)} eingetragen", participation)
    if role.is_billable and occurrence.trainer_missing_since:
        occurrence.trainer_missing_since = None
        occurrence.save(update_fields=["trainer_missing_since"])
    if freed:
        promote(occurrence)
    return participation


def remove_team(participation: Participation, by: User | None = None) -> None:
    if participation.is_confirmed:
        raise RegistrationError("Bestätigte Stunden bleiben für die Abrechnung erhalten.")
    _audit(
        by,
        "team_remove",
        f"{participation.person.display_name} als {participation.role.name} von {_when(participation.occurrence)} "
        "ausgetragen",
        participation,
    )
    participation.delete()


def confirm(participation: Participation, minutes: int | None = None, by: User | None = None) -> None:
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
    before = participation.minutes if participation.is_confirmed else None
    participation.confirmed_at = participation.confirmed_at or timezone.now()
    participation.minutes = minutes or participation.occurrence.minutes
    participation.save(update_fields=["confirmed_at", "minutes", "updated_at"])
    if before is None:
        summary = f"Stunden für {_when(participation.occurrence)} bestätigt ({participation.minutes} Minuten)"
        _audit(by, "confirm", summary, participation)
    elif before != participation.minutes:
        summary = f"Dauer für {_when(participation.occurrence)} geändert"
        audit.log(
            by,
            audit.Area.EVENTS,
            "confirm_update",
            summary,
            member=participation.member_id,
            changes={"Minuten": [before, participation.minutes]},
        )


def unconfirm(participation: Participation, by: User | None = None) -> None:
    """Bestätigung zurücknehmen (z. B. versehentlich bestätigt), bis der Monat zur Abrechnung eingereicht ist."""
    _check_unlocked(participation)
    if not participation.is_confirmed:
        return
    minutes = participation.minutes
    participation.confirmed_at = None
    participation.minutes = None
    participation.save(update_fields=["confirmed_at", "minutes", "updated_at"])
    _audit(
        by,
        "unconfirm",
        f"Bestätigung für {_when(participation.occurrence)} zurückgenommen ({minutes} Minuten)",
        participation,
    )


@transaction.atomic
def adjust_hours(
    participation: Participation, *, minutes: int, role: ParticipantRole, member: Member, by: User | None = None
) -> Participation:
    """„Anpassen“ nach dem Termin: Dauer, Rolle oder Übungsleiter in einem Schritt (ADR 0014).

    Eigene Dauer und Rolle gelten als bestätigt. War jemand anderes da, übernimmt die Vertretung den Platz und
    bestätigt ihre Stunden selbst (wie beim Übertragen); die eingegebene Dauer gilt dann nicht.
    """
    occurrence = participation.occurrence
    if occurrence.starts_at > timezone.now():
        raise RegistrationError("Anpassen kannst du erst, wenn der Termin begonnen hat.")
    if member.pk != participation.member_id:
        return hand_over(participation, member, role, by)
    if role.pk != participation.role_id:
        if not role.is_billable:
            raise RegistrationError(f"Für {role.name} werden keine Stunden abgerechnet.")
        _check_unlocked(participation)
        _check_role(member, role, occurrence.event, timezone.localdate(occurrence.starts_at))
        unconfirm(participation, by)
        participation = set_team(occurrence, member, role, by)
    confirm(participation, minutes, by)
    return participation


# Vertretungen und Austragen (ADR 0018): vor dem Termin wie nachträglich („Nicht dabei?“, ADR 0012)


def _check_changeable(participation: Participation, by: User | None) -> None:
    """Austragen und Übertragen: nur Übungsleiter, nicht bei Absage oder Sperre; bestätigte Stunden nur selbst."""
    if not participation.role.is_team:
        raise RegistrationError("Das geht nur für die Übungsleiter eines Termins.")
    if participation.occurrence.is_cancelled:
        raise RegistrationError("Der Termin ist abgesagt.")
    _check_unlocked(participation)
    if participation.is_confirmed and (by is None or own_member(by) != participation.member):
        name = participation.person.display_name
        raise RegistrationError(f"{name} hat schon Stunden bestätigt – sprecht euch bitte kurz ab.")


def has_trainer(occurrence: Occurrence, without: Participation | None = None) -> bool:
    """Ist mindestens ein Übungsleiter mit abrechnungsrelevanter Rolle eingeteilt (außer ``without``)?"""
    team = occurrence.participations.filter(role__is_team=True, role__is_billable=True, status__in=ACTIVE)
    if without is not None:
        team = team.exclude(pk=without.pk)
    return team.exists()


def leaves_without_trainer(participation: Participation, now: datetime | None = None) -> bool:
    """Wäre der Termin ohne Trainer, wenn diese Teilnahme wegfällt? Nur vor dem Termin von Belang."""
    occurrence = participation.occurrence
    if not participation.role.is_billable or occurrence.is_cancelled or occurrence.starts_at <= (now or timezone.now()):
        return False
    return not has_trainer(occurrence, without=participation)


@transaction.atomic
def withdraw(participation: Participation, by: User | None = None) -> None:
    """Austragen ohne Vertretung. Nach dem Termin heißt das „Ich war nicht dabei“: eine eigene Bestätigung wird
    zurückgenommen. Ist danach kein Trainer mehr eingeteilt, erfährt es die Abteilungsleitung."""
    _check_changeable(participation, by)
    occurrence = participation.occurrence
    missing = leaves_without_trainer(participation)
    unconfirm(participation, by)
    remove_team(participation, by)
    if occurrence.counts_team:
        promote(occurrence)
    if missing:
        occurrence.trainer_missing_since = timezone.now()
        occurrence.save(update_fields=["trainer_missing_since"])
        absent = participation.person.display_name
        transaction.on_commit(lambda: notices.trainer_missing(occurrence, absent, by))


@transaction.atomic
def hand_over(
    participation: Participation, member: Member, role: ParticipantRole | None = None, by: User | None = None
) -> Participation:
    """Übertragen bzw. Vertreten: ``member`` übernimmt den Platz, gilt sofort (die Übungsleiter sprechen sich ab).

    Wer nicht selbst gehandelt hat, bekommt eine Nachricht. Nach dem Termin bestätigt die Vertretung die Stunden.
    """
    _check_changeable(participation, by)
    occurrence = participation.occurrence
    role = role or participation.role
    if member.pk == participation.member_id:
        raise RegistrationError("Wähle bitte, wer übernimmt.")
    existing = occurrence.participations.filter(member=member, role__is_team=True, status__in=ACTIVE).first()
    if existing:
        raise RegistrationError(f"{member.display_name} ist schon als {existing.role.name} eingetragen.")
    _check_role(member, role, occurrence.event, timezone.localdate(occurrence.starts_at))
    unconfirm(participation, by)
    absent = participation.member
    remove_team(participation, by)
    substitute = set_team(occurrence, member, role, by)
    started = occurrence.starts_at <= timezone.now()
    verb = "wurde" if started else "wird"
    name = absent.display_name if absent else participation.person.display_name
    _audit(by, "hand_over", f"{name} {verb} bei {_when(occurrence)} von {member.display_name} vertreten", substitute)
    if absent is not None:
        transaction.on_commit(lambda: notices.handed_over(substitute, absent, by))
    return substitute


@transaction.atomic
def cancel_after(occurrence: Occurrence, by: User | None = None) -> None:
    """Nachträglich absagen: „Der Termin hat nicht stattgefunden.“ Ohne Nachrichten an Teilnehmer."""
    if occurrence.starts_at > timezone.now():
        raise RegistrationError("Vor dem Termin sagst du ihn über „Absagen“ ab.")
    confirmed = occurrence.participations.filter(role__is_team=True, confirmed_at__isnull=False).exclude(
        member__isnull=True
    )
    for participation in confirmed.select_related("member", "role"):
        _check_unlocked(participation)
        if by is None or participation.member != own_member(by):
            name = participation.person.display_name
            raise RegistrationError(f"{name} hat schon Stunden bestätigt – sprecht euch bitte kurz ab.")
        unconfirm(participation, by)
    cancel(occurrence, by, notify=False)


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
    if team:
        day = timezone.localdate(once["starts_at"]) if dates == "once" and once else None
        _check_role(*team, event, day)
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
    if not role.is_team:
        raise RegistrationError(f"{role.name} ist keine Übungsleiter-Rolle.")
    _check_role(member, role, schedule.event)
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
    """Aus dem Standard-Team nehmen; zukünftige, unbestätigte Team-Teilnahmen fallen weg (frei gewordene Plätze
    gehen an die Warteliste, wenn die Übungsleiter zur Höchstzahl zählen)."""
    removed = Participation.objects.filter(
        occurrence__in=_future(entry.schedule), member=entry.member, role__is_team=True, confirmed_at=None
    )
    occurrences = list(Occurrence.objects.filter(participations__in=removed).select_related("event").distinct())
    removed.delete()
    entry.delete()
    for occurrence in occurrences:
        if occurrence.counts_team:
            promote(occurrence)


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
        return not active and not self.occurrence.is_cancelled and self.window == "open" and not self.blocked

    @property
    def blocked_hint(self) -> bool:
        """Statt „Anmelden“ den Hinweis zeigen, dass nur Übungs- oder Abteilungsleiter anmelden können."""
        active = self.participation is not None and self.participation.is_active
        return self.blocked and not active and not self.occurrence.is_cancelled and self.window == "open"

    @property
    def blocked(self) -> bool:
        """Passt nicht, und die Zielgruppe ist eine Vorgabe: anmelden nur über Übungs- oder Abteilungsleiter."""
        return self.match == Match.NO and not is_recommendation(self.occurrence)

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

    @property
    def month(self) -> date:
        """Erster Tag des Monats, zum Gliedern der Liste."""
        return timezone.localdate(self.occurrence.starts_at).replace(day=1)

    @property
    def team(self) -> list[Participation]:
        """Eingeteilte Übungsleiter (aus dem Prefetch), für die Liste ohne eigene Mitglieder."""
        return [p for p in self.occurrence.participations.all() if p.role.is_team and p.is_active]


@dataclass
class Agenda:
    entries: list[AgendaEntry] = field(default_factory=list)
    several: bool = False  # mehrere eigene Mitglieder: Namen an jeder Zeile
    has_members: bool = False  # ohne eigene Mitglieder: alle Termine ohne Anmeldeknöpfe


@dataclass
class AgendaFilter:
    """Filter der Seite „Termine“; mehrere gelten zusammen (UND). Ohne Enddatum: alle kommenden Termine."""

    matching: bool = True  # „Für mich“: passt zu einem eigenen Mitglied oder es ist eingetragen
    mine: bool = False  # „Nur angemeldete“: ein eigenes Mitglied ist angemeldet, auf der Warteliste oder Übungsleiter
    no_training: bool = False  # „Ohne Trainings“: alles außer der Veranstaltungsart „Training“
    event: int | None = None  # nur diese Veranstaltung (Schnellzugang per Code)
    end: date | None = None
    hide_cancelled: bool = False


TRAINING = "Training"


def occurrences(flt: AgendaFilter, now: datetime | None = None) -> QuerySet[Occurrence]:
    """Kommende Termine nach Art, Veranstaltung und Absage; die übrigen Filter brauchen die eigenen Mitglieder."""
    now = now or timezone.now()
    rows = Occurrence.objects.select_related("event__event_type").prefetch_related(
        "event__target_groups__interests",
        "target_groups__interests",
        "participations__role",
        "participations__member",
    )
    rows = rows.filter(ends_at__gte=now)
    if flt.end:
        rows = rows.filter(starts_at__lt=_aware(flt.end + timedelta(days=1), time.min))
    if flt.no_training:
        rows = rows.exclude(event__event_type__name__iexact=TRAINING)
    if flt.event:
        rows = rows.filter(event_id=flt.event)
    if flt.hide_cancelled:
        rows = rows.filter(cancelled_at__isnull=True)
    return rows.order_by("starts_at", "pk")


def agenda(user: Any, flt: AgendaFilter | None = None) -> Agenda:
    """Termine nach Datum, jeder einmal; darunter die eigenen Mitglieder mit Status und Knopf.

    Mit „nur passende“ fehlen Termine, die zu keinem eigenen Mitglied passen und für die keines eingetragen ist.
    Ohne eigene Mitglieder: alle Termine ohne Zeilen.
    """
    flt = flt or AgendaFilter()
    ensure_generated()
    links = members.effective_links(user)
    shown = links
    rows = list(occurrences(flt))
    participations = {
        (p.occurrence_id, p.member_id): p
        for p in Participation.objects.filter(
            member_id__in=[link.member.pk for link in shown], occurrence__in=rows
        ).select_related("role")
    }
    interests = {link.member.pk: {interest.pk for interest in link.member.interests.all()} for link in shown}
    result = Agenda(several=len(shown) > 1, has_members=bool(links))
    for occurrence in rows:
        state = window(occurrence)
        entry = AgendaEntry(occurrence)
        for link in shown:
            member = link.member
            match = match_occurrence(occurrence, member, interests[member.pk])
            participation = participations.get((occurrence.pk, member.pk))
            active = participation is not None and participation.is_active
            if active or match != Match.NO or not flt.matching:
                entry.rows.append(AgendaRow(link, AgendaItem(occurrence, match, participation, state)))
        if links and not entry.rows:
            continue
        if (
            links
            and flt.mine
            and not any(row.item.participation and row.item.participation.is_active for row in entry.rows)
        ):
            continue
        result.entries.append(entry)
    return result


def next_entries(user: Any, count: int = 3) -> list[AgendaEntry]:
    """Für die Startseite: die nächsten Termine, die zu einem eigenen Mitglied passen – jeder nur einmal."""
    if not members.effective_links(user):
        return []
    flt = AgendaFilter(end=timezone.localdate() + timedelta(days=21), hide_cancelled=True)
    return agenda(user, flt).entries[:count]


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


def trainings_on(day: date) -> list[Occurrence]:
    """Für den Trainingstausch: alle Trainings eines Tages, auch abgesagte (die ohne Knöpfe)."""
    ensure_generated()
    return list(
        Occurrence.objects.filter(
            starts_at__gte=_aware(day, time.min),
            starts_at__lt=_aware(day + timedelta(days=1), time.min),
            event__event_type__name__iexact=TRAINING,
        )
        .select_related("event")
        .order_by("starts_at", "pk")
    )


def team(occurrence: Occurrence) -> list[Participation]:
    return list(
        occurrence.participations.filter(status__in=ACTIVE, role__is_team=True)
        .select_related("member", "role")
        .order_by("role__order", "member__first_name")
    )


def open_confirmations(user: Any, now: datetime | None = None) -> list[Participation]:
    """Für die Startseite: vergangene, abrechnungsrelevante Termine der letzten 90 Tage, die noch auf „Stunden
    bestätigen“ warten; ohne gesperrte (eingereichte Monate), ältester zuerst."""
    member = own_member(user)
    if member is None:
        return []
    now = now or timezone.now()
    rows = (
        Participation.objects.filter(
            member=member,
            role__is_team=True,
            role__is_billable=True,
            status=ParticipationStatus.REGISTERED,
            confirmed_at__isnull=True,
            occurrence__cancelled_at__isnull=True,
            occurrence__starts_at__lte=now,
            occurrence__starts_at__gte=now - timedelta(days=90),
        )
        .select_related("occurrence__event", "role", "member")
        .order_by("occurrence__starts_at")
    )
    return [p for p in rows if not locked_reason(p)]


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
