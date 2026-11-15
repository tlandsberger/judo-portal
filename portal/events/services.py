"""Fachlogik der Veranstaltungen: Zielgruppen, Termine aus Zeitplänen, Anmeldung mit Warteliste, Begleitung, Rechte.

Auf Mitglieder greift das Modul nur über ``portal.members.services`` zu (eigene Mitglieder, Eltern).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import IntEnum
from functools import partial
from typing import Any

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.db.models import Q, QuerySet
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from portal.accounts.models import Role, User
from portal.members import services as members
from portal.members.models import Member, MemberLink, grade_rank

from .models import (
    Event,
    EventStaff,
    Occurrence,
    Registration,
    RegistrationStatus,
    Schedule,
    StaffFunction,
    Staffing,
    TargetGroup,
)

log = logging.getLogger(__name__)

# Veranstaltungen, Zeitpläne und Zielgruppen pflegt die Abteilungsleitung (ADR 0010).
MANAGE_EVENTS = (Role.DEPARTMENT_HEAD, Role.ADMIN)
HORIZON_DAYS = 365
# So lange nach dem Termin sehen begleitende Übungsleiter noch die Teilnehmerliste.
PARTICIPANTS_DAYS_AFTER = 14
AGENDA_DAYS = 42
ACTIVE = (RegistrationStatus.REGISTERED, RegistrationStatus.WAITLIST)


class RegistrationError(Exception):
    """Anmeldung oder Abmeldung ist gerade nicht möglich; die Nachricht ist für die Oberfläche."""


# Rechte


def can_manage_events(user: Any) -> bool:
    return bool(user.is_authenticated and user.has_role(*MANAGE_EVENTS))


def is_trainer(user: Any) -> bool:
    return bool(user.is_authenticated and user.has_role(Role.TRAINER))


def can_plan_staff(user: Any) -> bool:
    """Standard-Team und Begleitung planen: Abteilungsleitung und Übungsleiter."""
    return can_manage_events(user) or is_trainer(user)


def accompanies(user: Any, occurrence: Occurrence) -> bool:
    return bool(user.is_authenticated and occurrence.staffings.filter(user=user).exists())


def can_lead(user: Any, occurrence: Occurrence) -> bool:
    """Termin absagen, Hinweis und Team ändern, Ausnahmen eintragen: Abteilungsleitung und Begleiter."""
    return can_manage_events(user) or (is_trainer(user) and accompanies(user, occurrence))


def can_see_participants(user: Any, occurrence: Occurrence, now: datetime | None = None) -> bool:
    """Teilnehmerliste mit Notfallkontakt: Abteilungsleitung; Begleiter bis 14 Tage nach dem Termin."""
    if can_manage_events(user):
        return True
    now = now or timezone.now()
    return can_lead(user, occurrence) and now <= occurrence.ends_at + timedelta(days=PARTICIPANTS_DAYS_AFTER)


def trainers() -> list[User]:
    return [user for user in User.objects.filter(is_active=True) if user.has_role(Role.TRAINER)]


# Zielgruppen


class Match(IntEnum):
    NO = 0
    MAYBE = 1  # passt, sobald das Gewicht eingetragen ist
    YES = 2


def age_in_year(member: Member, on: date) -> int:
    """Alter nach Jahrgang, wie bei Judo-Altersklassen (U11, U13 …)."""
    return on.year - member.birth_date.year


def match_group(group: TargetGroup, member: Member, on: date, interest_ids: set[int] | None = None) -> Match:
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
    if group_interests:
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


def match_event(event: Event, member: Member, on: date, interest_ids: set[int] | None = None) -> Match:
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


def add_default_staff(occurrence: Occurrence) -> None:
    for staff in occurrence.event.staff.all():
        Staffing.objects.get_or_create(occurrence=occurrence, user=staff.user, defaults={"function": staff.function})


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
            occurrence = Occurrence.objects.create(
                event=schedule.event,
                schedule=schedule,
                starts_at=_aware(day, schedule.start_time),
                ends_at=_aware(day, schedule.end_time),
            )
            add_default_staff(occurrence)
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
        .exclude(registrations__status__in=ACTIVE)
        .exclude(staffings__confirmed_at__isnull=False)
    )


@transaction.atomic
def regenerate(schedule: Schedule) -> list[Occurrence]:
    """Nach einer Änderung am Zeitplan: zukünftige Termine neu erzeugen.

    Gibt die zukünftigen Termine zurück, die bleiben mussten (Anmeldungen, Abweichungen) und nicht mehr zum
    Zeitplan passen; über sie entscheidet die Abteilungsleitung.
    """
    _replaceable(schedule.occurrences.all()).delete()
    generate(schedule)
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
def update_occurrence(occurrence: Occurrence, fields: Iterable[str]) -> None:
    """Abweichung an einem einzelnen Termin (Uhrzeit, Ort, Hinweis) – der Termin bleibt dann bei Neuerzeugung."""
    changed = set(fields)
    if changed & {"starts_at", "ends_at", "location"}:
        occurrence.is_modified = True
    occurrence.save()


# Absage


@transaction.atomic
def cancel(occurrence: Occurrence, by: User | None = None) -> None:
    if occurrence.is_cancelled:
        return
    occurrence.cancelled_at = timezone.now()
    occurrence.save(update_fields=["cancelled_at"])
    recipients = _participant_users(occurrence) | {
        staffing.user for staffing in occurrence.staffings.select_related("user")
    }
    recipients.discard(by)
    log.info("Termin %s abgesagt", occurrence.pk)
    transaction.on_commit(
        lambda: _send(recipients, f"Abgesagt: {occurrence.event.title}", "cancelled", {"occurrence": occurrence})
    )


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
    return occurrence.registrations.filter(status=RegistrationStatus.REGISTERED).count()


def check_register(occurrence: Occurrence, member: Member, match: Match | None = None) -> None:
    """Prüft, ob sich das Mitglied selbst (bzw. über die Eltern) anmelden kann."""
    if occurrence.is_cancelled:
        raise RegistrationError("Der Termin ist abgesagt.")
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


@transaction.atomic
def register(
    occurrence: Occurrence,
    member: Member,
    by: User,
    *,
    weight: Decimal | None = None,
    note: str = "",
    exception: bool = False,
) -> Registration:
    """Meldet ein Mitglied an. Ausnahmen (Abteilungsleitung, Begleiter) gelten unabhängig von Zielgruppe,
    Anmeldezeitraum und Höchstzahl. Ist der Termin voll, kommt das Mitglied auf die Warteliste."""
    if exception:
        if occurrence.is_cancelled:
            raise RegistrationError("Der Termin ist abgesagt.")
    else:
        check_register(occurrence, member)
    existing = Registration.objects.filter(occurrence=occurrence, member=member).first()
    if existing and existing.is_active and not exception:
        return existing
    if weight is not None and weight != member.weight:
        member.weight = weight
        member.save(update_fields=["weight", "updated_at"])
    if occurrence.event.weight_required and weight is None:
        weight = member.weight
    capacity = occurrence.event.capacity
    full = capacity is not None and registered_count(occurrence) >= capacity
    status = RegistrationStatus.WAITLIST if full and not exception else RegistrationStatus.REGISTERED
    registration, _ = Registration.objects.update_or_create(
        occurrence=occurrence,
        member=member,
        defaults={
            "status": status,
            "registered_by": by,
            "exception_by": by if exception else None,
            "weight": weight,
            "note": note,
            "created_at": timezone.now(),
        },
    )
    log.info("Mitglied %s für Termin %s: %s", member.pk, occurrence.pk, status)
    return registration


@transaction.atomic
def unregister(registration: Registration, by: User, *, force: bool = False) -> None:
    """Abmelden bis zum Anmeldeschluss; danach nur Abteilungsleitung und Begleiter (``force``)."""
    if not force and window(registration.occurrence) == "closed":
        raise RegistrationError(
            "Nach dem Anmeldeschluss kannst du dich nicht mehr abmelden. Sag bitte dem Übungsleiter Bescheid."
        )
    was_registered = registration.status == RegistrationStatus.REGISTERED
    registration.status = RegistrationStatus.CANCELLED
    registration.registered_by = by
    registration.save(update_fields=["status", "registered_by", "updated_at"])
    if was_registered:
        promote(registration.occurrence)


def promote(occurrence: Occurrence) -> list[Registration]:
    """Rückt von der Warteliste nach, solange Plätze frei sind, und benachrichtigt per Mail."""
    capacity = occurrence.event.capacity
    promoted: list[Registration] = []
    if capacity is None:
        return promoted
    free = capacity - registered_count(occurrence)
    waiting = occurrence.registrations.filter(status=RegistrationStatus.WAITLIST).select_related("member")
    for registration in waiting[: max(free, 0)]:
        registration.status = RegistrationStatus.REGISTERED
        registration.save(update_fields=["status", "updated_at"])
        promoted.append(registration)
        users = set(members.member_users(registration.member))
        context = {"occurrence": occurrence, "member": registration.member}
        subject = f"Nachgerückt: {occurrence.event.title}"
        transaction.on_commit(partial(_send, users, subject, "promoted", context))
    return promoted


# Begleitung


@transaction.atomic
def set_staffing(occurrence: Occurrence, user: User, function: StaffFunction | str) -> Staffing:
    if not user.has_role(Role.TRAINER):
        raise ValueError(f"{user.display_name} ist kein Übungsleiter.")
    staffing, _ = Staffing.objects.update_or_create(
        occurrence=occurrence, user=user, defaults={"function": StaffFunction(function)}
    )
    return staffing


def remove_staffing(staffing: Staffing) -> None:
    if staffing.is_confirmed:
        raise ValueError("Eine bestätigte Begleitung bleibt für die Abrechnung erhalten.")
    staffing.delete()


def confirm(staffing: Staffing, minutes: int | None = None) -> None:
    """Nach dem Termin: „durchgeführt, ich war als Trainer/Kotrainer da“."""
    if staffing.occurrence.starts_at > timezone.now():
        raise ValueError("Bestätigen kannst du erst, wenn der Termin begonnen hat.")
    if staffing.occurrence.is_cancelled:
        raise ValueError("Der Termin ist abgesagt.")
    staffing.confirmed_at = timezone.now()
    staffing.minutes = minutes or staffing.occurrence.minutes
    staffing.save(update_fields=["confirmed_at", "minutes"])


@transaction.atomic
def set_default_staff(event: Event, user: User, function: StaffFunction | str) -> None:
    """Standard-Team ändern; zukünftige Termine übernehmen den Übungsleiter (bestehende Einteilungen bleiben)."""
    if not user.has_role(Role.TRAINER):
        raise ValueError(f"{user.display_name} ist kein Übungsleiter.")
    EventStaff.objects.update_or_create(event=event, user=user, defaults={"function": StaffFunction(function)})
    for occurrence in event.occurrences.filter(starts_at__gte=timezone.now(), cancelled_at__isnull=True):
        Staffing.objects.get_or_create(occurrence=occurrence, user=user, defaults={"function": function})


@transaction.atomic
def remove_default_staff(staff: EventStaff) -> None:
    """Aus dem Standard-Team nehmen; zukünftige, unbestätigte Einteilungen fallen weg."""
    Staffing.objects.filter(
        occurrence__event=staff.event, occurrence__starts_at__gte=timezone.now(), user=staff.user, confirmed_at=None
    ).delete()
    staff.delete()


# Ansichten


@dataclass
class AgendaItem:
    occurrence: Occurrence
    match: Match
    registration: Registration | None = None
    window: str = "open"

    @property
    def status(self) -> str:
        if self.registration and self.registration.is_active:
            return self.registration.status
        return "cancelled" if self.registration else ""

    @property
    def can_register(self) -> bool:
        active = self.registration is not None and self.registration.is_active
        return not active and not self.occurrence.is_cancelled and self.window == "open" and self.match != Match.NO

    @property
    def can_unregister(self) -> bool:
        active = self.registration is not None and self.registration.is_active
        return active and self.window != "closed" and not self.occurrence.is_cancelled

    @property
    def quick(self) -> bool:
        """Anmelden mit einem Klick: ohne Pflichtgewicht. Sonst über das Formular."""
        return not self.occurrence.event.weight_required


@dataclass
class AgendaSection:
    link: MemberLink
    items: list[AgendaItem] = field(default_factory=list)
    others: list[AgendaItem] = field(default_factory=list)

    @property
    def member(self) -> Member:
        return self.link.member


def upcoming(days: int = AGENDA_DAYS) -> QuerySet[Occurrence]:
    now = timezone.now()
    return (
        Occurrence.objects.filter(ends_at__gte=now, starts_at__lte=now + timedelta(days=days))
        .select_related("event")
        .prefetch_related("event__target_groups__interests", "staffings__user")
    )


def agenda(user: Any, days: int = AGENDA_DAYS) -> list[AgendaSection]:
    """Je eigenem Mitglied die nächsten Termine: passende oben, alle anderen unter „Weitere“."""
    links = members.effective_links(user)
    if not links:
        return []
    ensure_generated()
    occurrences = list(upcoming(days))
    member_ids = [link.member.pk for link in links]
    registrations = {
        (r.occurrence_id, r.member_id): r
        for r in Registration.objects.filter(member_id__in=member_ids, occurrence__in=occurrences)
    }
    sections = []
    for link in links:
        member = link.member
        interest_ids = {interest.pk for interest in member.interests.all()}
        section = AgendaSection(link=link)
        for occurrence in occurrences:
            match = match_event(occurrence.event, member, timezone.localdate(occurrence.starts_at), interest_ids)
            registration = registrations.get((occurrence.pk, member.pk))
            item = AgendaItem(occurrence, match, registration, window(occurrence))
            if match != Match.NO or (registration and registration.is_active):
                section.items.append(item)
            else:
                section.others.append(item)
        sections.append(section)
    return sections


def next_items(user: Any, count: int = 3) -> list[tuple[Member, AgendaItem]]:
    """Für die Startseite: die nächsten passenden Termine über alle eigenen Mitglieder."""
    items = [
        (section.member, item)
        for section in agenda(user, days=21)
        for item in section.items
        if not item.occurrence.is_cancelled
    ]
    return sorted(items, key=lambda pair: pair[1].occurrence.starts_at)[:count]


@dataclass
class Participant:
    registration: Registration
    age: int
    weight: Decimal | None
    guardians: list[User]

    @property
    def member(self) -> Member:
        return self.registration.member


def participants(occurrence: Occurrence) -> list[Participant]:
    """Teilnehmerliste mit Judo-Daten und Notfallkontakt (Telefon des Mitglieds, Eltern)."""
    on = timezone.localdate(occurrence.starts_at)
    rows = occurrence.registrations.filter(status__in=ACTIVE).select_related("member", "exception_by")
    return [
        Participant(
            registration=registration,
            age=age_in_year(registration.member, on),
            weight=registration.weight or registration.member.weight,
            guardians=members.guardians(registration.member),
        )
        for registration in rows
    ]


def own_staffings(user: User) -> tuple[list[Staffing], list[Staffing]]:
    """„Meine Einsätze“: kommende und die letzten 90 Tage."""
    now = timezone.now()
    staffings = Staffing.objects.filter(user=user).select_related("occurrence__event")
    coming = list(staffings.filter(occurrence__ends_at__gte=now).order_by("occurrence__starts_at")[:50])
    past = list(
        staffings.filter(occurrence__ends_at__lt=now, occurrence__starts_at__gte=now - timedelta(days=90)).order_by(
            "-occurrence__starts_at"
        )
    )
    return coming, past


# Mails


def _participant_users(occurrence: Occurrence) -> set[User]:
    users: set[User] = set()
    for registration in occurrence.registrations.filter(status__in=ACTIVE).select_related("member"):
        users.update(members.member_users(registration.member))
    return users


def _send(users: Iterable[User], subject: str, template: str, context: dict[str, Any]) -> None:
    occurrence = context["occurrence"]
    context = {
        **context,
        "url": settings.BASE_URL + reverse("occurrence_detail", args=[occurrence.pk]),
        "base_url": settings.BASE_URL,
        "starts": timezone.localtime(occurrence.starts_at),
    }
    for user in users:
        message = EmailMultiAlternatives(
            subject=settings.EMAIL_SUBJECT_PREFIX + subject,
            body=render_to_string(f"events/email/{template}.txt", {**context, "user": user}),
            to=[user.email],
        )
        message.attach_alternative(
            render_to_string(f"events/email/{template}.html", {**context, "user": user}), "text/html"
        )
        message.send()
