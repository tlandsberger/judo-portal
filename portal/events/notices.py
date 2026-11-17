"""Benachrichtigungen rund um Termine: Push-Benachrichtigung, sonst Mail (über ``portal.notifications``, ADR 0011).

Sofort: Absage, Änderung, Nachrücken. Über den Zeitplaner (alle 5 Minuten): Anmeldung offen, Erinnerung an den
Anmeldeschluss, Stunden bestätigen. Jede Nachricht geht je Benutzer und Anlass nur einmal raus.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Any

from django.db import transaction
from django.urls import reverse
from django.utils import formats, timezone

from portal.accounts.models import User
from portal.members import services as members
from portal.members.models import Member, MemberLink
from portal.notifications import services as notifications
from portal.notifications.models import SentNotification
from portal.notifications.services import Action, ActionResult

from . import guests, services
from .models import Occurrence, Participation, ParticipationStatus

log = logging.getLogger(__name__)

CONFIRM_HOUR = 20
CONFIRM_MORNING_HOUR = 8
CONFIRM_LOOKBACK = timedelta(days=3)
DEADLINE_AHEAD = timedelta(hours=24)


# Texte


def _when(occurrence: Occurrence) -> str:
    local = timezone.localtime(occurrence.starts_at)
    return f"{formats.date_format(local, 'D, d.m.')} um {local:%H:%M} Uhr"


def _url(occurrence: Occurrence) -> str:
    return reverse("occurrence_detail", args=[occurrence.pk])


def _names(people: Iterable[Member]) -> str:
    names = [member.first_name for member in people]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " und " + names[-1]


def _stamp(moment: datetime | None = None) -> int:
    return int((moment or timezone.now()).timestamp())


def _team_and_participants(occurrence: Occurrence, by: User | None) -> set[User]:
    users = services.participant_users(occurrence)
    users.discard(by)
    return users


# Sofort


def cancelled(occurrence: Occurrence, by: User | None = None) -> None:
    title = occurrence.event.title
    body = f"{title} am {_when(occurrence)} fällt aus."
    if occurrence.note:
        body += f" Hinweis: {occurrence.note}"
    for user in _team_and_participants(occurrence, by):
        notifications.notify(
            user,
            key=f"cancelled:{occurrence.pk}:{user.pk}:{_stamp(occurrence.cancelled_at)}",
            kind="cancelled",
            title=f"Abgesagt: {title}",
            body=body,
            url=_url(occurrence),
        )
    guests.notify(occurrence, f"Abgesagt: {title}", body)


def changed(occurrence: Occurrence, by: User | None = None) -> None:
    """Uhrzeit oder Ort eines kommenden Termins haben sich geändert."""
    if occurrence.is_cancelled or occurrence.starts_at <= timezone.now():
        return
    title = occurrence.event.title
    local_end = timezone.localtime(occurrence.ends_at)
    body = f"{title} findet jetzt am {_when(occurrence)} bis {local_end:%H:%M} Uhr statt"
    body += f", Ort: {occurrence.place}." if occurrence.place else "."
    for user in _team_and_participants(occurrence, by):
        notifications.notify(
            user,
            key=f"changed:{occurrence.pk}:{user.pk}:{_stamp()}",
            kind="changed",
            title=f"Geändert: {title}",
            body=body,
            url=_url(occurrence),
        )
    guests.notify(occurrence, f"Geändert: {title}", body)


def promoted(participation: Participation) -> None:
    occurrence, member = participation.occurrence, participation.member
    title = occurrence.event.title
    if member is None and participation.guest:
        guest = participation.guest
        body = f"Ein Platz ist frei geworden: Du bist jetzt für {title} am {_when(occurrence)} angemeldet."
        transaction.on_commit(lambda: guests.send_mail(guest, f"Nachgerückt: {title}", body))
        return
    if member is None:
        return
    for user in members.member_users(member):
        notifications.notify(
            user,
            key=f"promoted:{participation.pk}:{user.pk}:{_stamp()}",
            kind="promoted",
            title=f"Nachgerückt: {title}",
            body=f"Ein Platz ist frei geworden: {member.first_name} ist jetzt für {title} am {_when(occurrence)} "
            "angemeldet.",
            url=_url(occurrence),
            actions=[Action("unregister", "Doch absagen", {"p": participation.pk})],
        )


# Über den Zeitplaner


def _audience(occurrence: Occurrence, links: list[MemberLink]) -> dict[User, list[tuple[Member, services.Match]]]:
    """Wer zu einem Termin passt und noch nicht angemeldet ist, gruppiert nach Benutzer (Eltern, Mitglied selbst)."""
    on = timezone.localdate(occurrence.starts_at)
    taken = set(occurrence.participations.filter(status__in=services.ACTIVE).values_list("member_id", flat=True))
    audience: dict[User, list[tuple[Member, services.Match]]] = defaultdict(list)
    for link in links:
        member = link.member
        if member.pk in taken or not member.is_active or not link.is_effective():
            continue
        match = services.match_event(occurrence.event, member, on)
        if match != services.Match.NO:
            audience[link.user].append((member, match))
    return audience


def _effective_links() -> list[MemberLink]:
    return list(
        MemberLink.objects.filter(user__is_active=True)
        .select_related("user", "member")
        .prefetch_related("member__interests")
        .order_by("member__birth_date")
    )


def _one_off_candidates(now: datetime) -> list[Occurrence]:
    """Termine ohne Zeitplan (Wettkampf, Lehrgang …); wiederkehrende Trainings bekommen keine Anmelde-Nachrichten."""
    return list(
        Occurrence.objects.filter(cancelled_at__isnull=True, starts_at__gt=now, schedule__isnull=True)
        .select_related("event")
        .prefetch_related("event__target_groups__interests")
    )


def _registration_notice(
    occurrence: Occurrence, user: User, entries: list[tuple[Member, services.Match]], *, kind: str, title: str
) -> None:
    event = occurrence.event
    closes = timezone.localtime(occurrence.registration_closes)
    names = _names(member for member, _ in entries)
    if kind == "registration_open":
        body = f"Für {names} ist die Anmeldung zu {event.title} am {_when(occurrence)} offen"
        body += (
            f", bis {formats.date_format(closes, 'd.m.')} um {closes:%H:%M} Uhr."
            if closes < occurrence.starts_at
            else "."
        )
    else:
        body = f"Die Anmeldung zu {event.title} am {_when(occurrence)} schließt {formats.date_format(closes, 'D')} "
        verb = "ist" if len(entries) == 1 else "sind"
        body += f"um {closes:%H:%M} Uhr. {names} {verb} noch nicht angemeldet."
    actions = []
    if len(entries) == 1 and entries[0][1] == services.Match.YES and not event.weight_required:
        actions.append(Action("register", "Anmelden", {"o": occurrence.pk, "m": entries[0][0].pk}))
    notifications.notify(
        user,
        key=f"{kind}:{occurrence.pk}:{user.pk}",
        kind=kind,
        title=title,
        body=body,
        url=_url(occurrence),
        actions=actions,
    )


def notify_registration_open(now: datetime | None = None) -> None:
    """Einzeltermine: passende, noch nicht angemeldete Mitglieder, sobald die Anmeldung öffnet."""
    now = now or timezone.now()
    links = _effective_links()
    for occurrence in _one_off_candidates(now):
        if services.window(occurrence, now) != "open":
            continue
        for user, entries in _audience(occurrence, links).items():
            _registration_notice(
                occurrence, user, entries, kind="registration_open", title=f"Anmeldung offen: {occurrence.event.title}"
            )


def notify_deadlines(now: datetime | None = None) -> None:
    """Etwa 24 Stunden vor dem Anmeldeschluss, wenn ein passendes Mitglied noch nicht angemeldet ist."""
    now = now or timezone.now()
    links = _effective_links()
    for occurrence in _one_off_candidates(now):
        closes = occurrence.registration_closes
        if services.window(occurrence, now) != "open" or not now < closes <= now + DEADLINE_AHEAD:
            continue
        for user, entries in _audience(occurrence, links).items():
            # Wer die Nachricht „Anmeldung offen“ erst vor Kurzem bekam, braucht keine Erinnerung.
            recent = SentNotification.objects.filter(
                key=f"registration_open:{occurrence.pk}:{user.pk}", created_at__gte=now - timedelta(hours=12)
            )
            if recent.exists():
                continue
            _registration_notice(
                occurrence, user, entries, kind="deadline", title=f"Nur noch kurz: {occurrence.event.title}"
            )


def confirm_due(ends_at: datetime) -> datetime:
    """Erinnerung zum Bestätigen: am Abend des Termins, bei späten Terminen am nächsten Morgen."""
    end = timezone.localtime(ends_at)
    evening = end.replace(hour=CONFIRM_HOUR, minute=0, second=0, microsecond=0)
    if end <= evening:
        return evening
    return (end + timedelta(days=1)).replace(hour=CONFIRM_MORNING_HOUR, minute=0, second=0, microsecond=0)


def notify_confirm_hours(now: datetime | None = None) -> None:
    """Abrechnungsrelevante Rollen: am Abend des Termins an das Bestätigen der Stunden erinnern."""
    now = now or timezone.now()
    open_rows = Participation.objects.filter(
        role__is_billable=True,
        status=ParticipationStatus.REGISTERED,
        confirmed_at__isnull=True,
        occurrence__cancelled_at__isnull=True,
        occurrence__ends_at__lte=now,
        occurrence__ends_at__gte=now - CONFIRM_LOOKBACK,
    ).select_related("occurrence__event", "member", "role")
    for participation in open_rows:
        occurrence = participation.occurrence
        user = services.member_user(participation.member) if participation.member else None
        if user is None or now < confirm_due(occurrence.ends_at):
            continue
        notifications.notify(
            user,
            key=f"confirm:{participation.pk}",
            kind="confirm",
            title="Stunden bestätigen",
            body=f"Warst du bei {occurrence.event.title} am {_when(occurrence)} als {participation.role.name} dabei? "
            "Bitte bestätige deine Stunden.",
            url=reverse("billing_index"),
            actions=[
                Action("confirm", "Bestätigen", {"p": participation.pk}),
                Action("absent", "Nicht dabei?", url=reverse("hours_absent", args=[occurrence.pk])),
            ],
        )


def substitute(participation: Participation, absent: str) -> None:
    """Die Vertretung soll ihre Stunden bestätigen; gleicher Schlüssel wie die Abend-Erinnerung, also nur einmal."""
    occurrence = participation.occurrence
    user = services.member_user(participation.member) if participation.member else None
    if user is None:
        return
    notifications.notify(
        user,
        key=f"confirm:{participation.pk}",
        kind="confirm",
        title="Stunden bestätigen",
        body=f"Du hast {absent} bei {occurrence.event.title} am {_when(occurrence)} als {participation.role.name} "
        "vertreten. Bitte bestätige deine Stunden.",
        url=reverse("billing_index"),
        actions=[Action("confirm", "Bestätigen", {"p": participation.pk})],
    )


def run_jobs() -> None:
    now = timezone.now()
    notify_registration_open(now)
    notify_deadlines(now)
    notify_confirm_hours(now)


# Knöpfe an Push-Benachrichtigungen


def _failed(message: str, url: str = "/") -> ActionResult:
    return ActionResult(False, message, url)


def action_register(user: User, data: dict[str, Any]) -> ActionResult:
    occurrence = Occurrence.objects.select_related("event").filter(pk=data.get("o", 0)).first()
    member = Member.objects.filter(pk=data.get("m", 0)).first()
    if occurrence is None or member is None or not members.can_self_edit(user, member):
        return _failed("Das hat nicht geklappt. Öffne bitte das Portal.", reverse("agenda"))
    if occurrence.event.weight_required:
        return _failed(
            "Für die Anmeldung brauchen wir noch das Gewicht.", reverse("register", args=[occurrence.pk, member.pk])
        )
    try:
        participation = services.register(occurrence, member, user)
    except services.RegistrationError as error:
        return _failed(str(error), _url(occurrence))
    if participation.status == ParticipationStatus.WAITLIST:
        return ActionResult(True, f"{member.first_name} steht auf der Warteliste für {occurrence.event.title}.")
    return ActionResult(True, f"{member.first_name} ist für {occurrence.event.title} angemeldet.")


def action_unregister(user: User, data: dict[str, Any]) -> ActionResult:
    rows = Participation.objects.select_related("occurrence__event", "member", "role")
    participation = rows.filter(pk=data.get("p", 0), role__is_team=False, member__isnull=False).first()
    member = participation.member if participation else None
    if participation is None or member is None or not members.can_self_edit(user, member):
        return _failed("Das hat nicht geklappt. Öffne bitte das Portal.", reverse("agenda"))
    if not participation.is_active:
        return ActionResult(True, f"{member.first_name} ist schon abgemeldet.")
    try:
        services.unregister(participation, user)
    except services.RegistrationError as error:
        return _failed(str(error), _url(participation.occurrence))
    return ActionResult(True, f"{member.first_name} ist von {participation.occurrence.event.title} abgemeldet.")


def action_confirm(user: User, data: dict[str, Any]) -> ActionResult:
    member = services.own_member(user)
    rows = Participation.objects.select_related("occurrence__event", "role")
    participation = rows.filter(pk=data.get("p", 0), member=member).first() if member else None
    if participation is None:
        return _failed("Das hat nicht geklappt. Öffne bitte das Portal.", reverse("billing_index"))
    if participation.is_confirmed:
        return ActionResult(True, "Deine Stunden sind schon bestätigt.")
    try:
        services.confirm(participation, by=user)
    except services.RegistrationError as error:
        return _failed(str(error), reverse("billing_index"))
    return ActionResult(
        True, f"Danke, {participation.occurrence.event.title} ist bestätigt ({participation.minutes} Minuten)."
    )


def register_all() -> None:
    from portal.core import scheduler

    notifications.register_action("register", action_register)
    notifications.register_action("unregister", action_unregister)
    notifications.register_action("confirm", action_confirm)
    scheduler.register_periodic(run_jobs)
