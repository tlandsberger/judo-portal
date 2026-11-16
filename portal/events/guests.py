"""Externe Gäste: Eintragen durch das Team, öffentlicher Anmeldelink mit Double-Opt-in, Gast-Seite (ADR 0013).

Gäste haben keinen Benutzer. Ihr geheimer Schlüssel (``Guest.token``) öffnet die Gast-Seite; jede Mail enthält den
Link. Nachrichten an Gäste gehen immer per Mail.
"""

from __future__ import annotations

import logging
import secrets
from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.db.models import Max
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from portal.accounts.models import User

from . import services
from .models import Event, Guest, Occurrence, Participation, ParticipationStatus

log = logging.getLogger(__name__)

PENDING_HOURS = 24
KEEP_DAYS = 90


def _token() -> str:
    return secrets.token_urlsafe(24)


# Anmeldelink der Veranstaltung


def enable_link(event: Event) -> str:
    if not event.guest_token:
        event.guest_token = _token()
        event.save(update_fields=["guest_token"])
    return event.guest_token


def renew_link(event: Event) -> str:
    """Neuer Anmeldelink, z. B. wenn der alte in falsche Hände geraten ist; der alte gilt nicht mehr."""
    event.guest_token = _token()
    event.save(update_fields=["guest_token"])
    return event.guest_token


def event_for_link(token: str) -> Event | None:
    if not token:
        return None
    return Event.objects.filter(guest_token=token, guests_welcome=True).first()


def open_occurrences(event: Event, now: datetime | None = None) -> list[Occurrence]:
    """Kommende Termine mit offener Anmeldung, zu denen sich Gäste selbst anmelden können."""
    now = now or timezone.now()
    rows = event.occurrences.filter(starts_at__gt=now, cancelled_at__isnull=True).select_related("event")
    return [occurrence for occurrence in rows if services.window(occurrence, now) == "open"]


# Anmelden


def _check(occurrence: Occurrence, guest: Guest) -> None:
    if occurrence.is_cancelled:
        raise services.RegistrationError("Der Termin ist abgesagt.")
    if services.window(occurrence) != "open":
        raise services.RegistrationError("Die Anmeldung zu diesem Termin ist nicht offen.")
    match = services.match_event(occurrence.event, guest, timezone.localdate(occurrence.starts_at))
    if match == services.Match.NO:
        raise services.RegistrationError(f"{occurrence.event.title} passt leider nicht zu {guest.first_name}.")


def _status(occurrence: Occurrence) -> ParticipationStatus:
    capacity = occurrence.event.capacity
    full = capacity is not None and services.registered_count(occurrence) >= capacity
    return ParticipationStatus.WAITLIST if full else ParticipationStatus.REGISTERED


@transaction.atomic
def register(event: Event, data: dict[str, Any], occurrences: Iterable[Occurrence], *, by: User | None = None) -> Guest:
    """Gast anlegen und für Termine anmelden.

    - Über den öffentlichen Link (``by`` leer): nur offene, passende Termine; die Anmeldung gilt erst nach der
      Bestätigung per Mail.
    - Vom Team (``by``): sofort gültig, auch nach dem Anmeldeschluss und über die Höchstzahl hinaus (Ausnahme).
    """
    occurrences = list(occurrences)
    if not occurrences:
        raise services.RegistrationError("Bitte wähle mindestens einen Termin.")
    if by is None and not event.guests_welcome:
        raise services.RegistrationError("Für diese Veranstaltung ist keine Anmeldung von Gästen möglich.")
    now = timezone.now()
    guest = Guest(event=event, token=_token(), consent_at=now, created_by=by, **data)
    if by is not None:
        guest.confirmed_at = now
    for occurrence in occurrences:
        if occurrence.event_id != event.pk:
            raise services.RegistrationError("Der Termin gehört nicht zu dieser Veranstaltung.")
        if by is None:
            _check(occurrence, guest)
        elif occurrence.is_cancelled:
            raise services.RegistrationError("Der Termin ist abgesagt.")
    guest.save()
    role = services.default_role()
    for occurrence in occurrences:
        Participation.objects.create(
            occurrence=occurrence,
            guest=guest,
            role=role,
            status=ParticipationStatus.REGISTERED if by else ParticipationStatus.PENDING,
            registered_by=by,
            exception_by=by,
            weight=guest.weight,
        )
    log.info("Gast %s für %s Termine von %s", guest.pk, len(occurrences), "Team" if by else "Link")
    transaction.on_commit(lambda: send_welcome(guest) if by else send_confirm_request(guest))
    return guest


@transaction.atomic
def confirm(guest: Guest) -> None:
    """Double-Opt-in: Erst jetzt zählen die Anmeldungen (bei vollem Termin: Warteliste)."""
    if guest.confirmed_at:
        return
    guest.confirmed_at = timezone.now()
    guest.save(update_fields=["confirmed_at"])
    for participation in guest.participations.filter(status=ParticipationStatus.PENDING).select_related(
        "occurrence__event"
    ):
        participation.status = _status(participation.occurrence)
        participation.save(update_fields=["status", "updated_at"])


@transaction.atomic
def add(guest: Guest, occurrence: Occurrence) -> Participation:
    """Der Gast meldet sich auf seiner Seite für einen weiteren Termin an."""
    if occurrence.event_id != guest.event_id:
        raise services.RegistrationError("Der Termin gehört nicht zu dieser Veranstaltung.")
    _check(occurrence, guest)
    existing = guest.participations.filter(occurrence=occurrence).first()
    if existing and existing.is_active:
        return existing
    participation, _ = Participation.objects.update_or_create(
        occurrence=occurrence,
        guest=guest,
        defaults={
            "role": services.default_role(),
            "status": _status(occurrence) if guest.confirmed_at else ParticipationStatus.PENDING,
            "weight": guest.weight,
            "created_at": timezone.now(),
        },
    )
    return participation


def unregister(participation: Participation) -> None:
    """Der Gast meldet sich ab – bis zum Anmeldeschluss."""
    if services.window(participation.occurrence) == "closed":
        raise services.RegistrationError("Nach dem Anmeldeschluss sag bitte direkt beim Trainer Bescheid.")
    was_registered = participation.status == ParticipationStatus.REGISTERED
    participation.status = ParticipationStatus.CANCELLED
    participation.save(update_fields=["status", "updated_at"])
    if was_registered:
        services.promote(participation.occurrence)


def update(guest: Guest, data: dict[str, Any]) -> None:
    for name, value in data.items():
        setattr(guest, name, value)
    guest.save()
    if "weight" in data:
        guest.participations.filter(occurrence__starts_at__gt=timezone.now()).update(weight=guest.weight)


# Aufräumen


def expire_pending(now: datetime | None = None) -> int:
    """Unbestätigte Anmeldungen verfallen nach 24 Stunden; der Gast wird mit ihnen gelöscht."""
    now = now or timezone.now()
    stale = Guest.objects.filter(confirmed_at__isnull=True, created_at__lt=now - timedelta(hours=PENDING_HOURS))
    count, _ = stale.delete()
    return count


def cleanup(now: datetime | None = None) -> int:
    """Gastdaten 90 Tage nach dem letzten Termin des Gastes löschen."""
    now = now or timezone.now()
    cutoff = now - timedelta(days=KEEP_DAYS)
    old = Guest.objects.annotate(last=Max("participations__occurrence__ends_at")).filter(last__lt=cutoff)
    count, _ = old.delete()
    if count:
        log.info("%s Gäste gelöscht (letzter Termin vor mehr als %s Tagen)", count, KEEP_DAYS)
    return count


# Mails


def page_url(guest: Guest) -> str:
    return settings.BASE_URL + reverse("guest_page", args=[guest.token])


def send_mail(guest: Guest, title: str, body: str) -> None:
    context = {"guest": guest, "title": title, "body": body, "url": page_url(guest)}
    message = EmailMultiAlternatives(
        subject=settings.EMAIL_SUBJECT_PREFIX + title,
        body=render_to_string("events/email/guest.txt", context),
        to=[guest.email],
    )
    message.attach_alternative(render_to_string("events/email/guest.html", context), "text/html")
    message.send()


def _dates(guest: Guest) -> str:
    rows = guest.participations.exclude(status=ParticipationStatus.CANCELLED).select_related("occurrence")
    return ", ".join(
        f"{timezone.localtime(p.occurrence.starts_at):%d.%m.%Y um %H:%M} Uhr" for p in rows.order_by("occurrence")
    )


def send_confirm_request(guest: Guest) -> None:
    send_mail(
        guest,
        f"Bitte bestätigen: {guest.event.title}",
        f"Danke für deine Anmeldung zu {guest.event.title} ({_dates(guest)}). Bitte bestätige sie innerhalb von "
        f"{PENDING_HOURS} Stunden über den Link – erst dann ist dein Platz reserviert. Hast du dich nicht angemeldet, "
        "ignoriere diese Mail einfach; die Daten werden dann gelöscht.",
    )


def send_welcome(guest: Guest) -> None:
    send_mail(
        guest,
        f"Angemeldet: {guest.event.title}",
        f"Du bist für {guest.event.title} angemeldet ({_dates(guest)}). Über den Link siehst du deine Anmeldung und "
        "deine Daten und kannst sie ändern oder absagen.",
    )


def notify(occurrence: Occurrence, title: str, body: str) -> None:
    """Absage oder Änderung eines Termins an seine Gäste (per Mail, nach dem Commit)."""
    for guest in services.participant_guests(occurrence):
        transaction.on_commit(lambda guest=guest: send_mail(guest, title, body))  # type: ignore[misc]


def run_periodic() -> None:
    expire_pending()


def run_daily() -> None:
    cleanup()


def register_all() -> None:
    from portal.core import scheduler

    scheduler.register_periodic(run_periodic)
    scheduler.register_daily(run_daily)
