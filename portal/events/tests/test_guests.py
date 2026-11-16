"""Gäste: öffentlicher Link mit Double-Opt-in, Eintragen durch das Team, Gast-Seite, Löschen (ADR 0013)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.core import mail
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from portal.events import guests, services
from portal.events.models import Event, Guest, ParticipationStatus, TargetGroup
from portal.events.services import RegistrationError
from portal.members.models import Interest

from .conftest import PASSWORD, make_occurrence, role

pytestmark = pytest.mark.django_db

DATA = {
    "first_name": "Lena",
    "last_name": "Gast",
    "birth_year": timezone.localdate().year - 12,
    "gender": "w",
    "grade": "",
    "weight": None,
    "club": "JC Pinneberg",
    "email": "lena@example.org",
    "phone": "0170 111",
    "guardian_name": "Petra Gast",
}


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()


def open_event(**extra) -> Event:
    event = Event.objects.create(title="Randori-Lehrgang", guests_welcome=True, **extra)
    guests.enable_link(event)
    return event


def form_data(occurrence, **extra) -> dict:
    data = {k: ("" if v is None else v) for k, v in DATA.items()}
    return {**data, "occurrences": [occurrence.pk], "consent": "on", "website": "", **extra}


def test_public_registration_needs_confirmation(django_capture_on_commit_callbacks):
    event = open_event(capacity=1)
    occurrence = make_occurrence(event, in_days=5)
    with django_capture_on_commit_callbacks(execute=True):
        guest = guests.register(event, DATA, [occurrence])
    participation = guest.participations.get()
    assert participation.status == ParticipationStatus.PENDING
    assert services.registered_count(occurrence) == 0
    assert mail.outbox[0].to == ["lena@example.org"]
    assert "Bitte bestätigen" in mail.outbox[0].subject
    assert reverse("guest_page", args=[guest.token]) in mail.outbox[0].body
    guests.confirm(guest)
    participation.refresh_from_db()
    assert participation.status == ParticipationStatus.REGISTERED
    second = guests.register(event, {**DATA, "email": "ole@example.org", "first_name": "Ole"}, [occurrence])
    guests.confirm(second)
    assert second.participations.get().status == ParticipationStatus.WAITLIST


def test_target_group_window_and_interests():
    event = open_event()
    kata = Interest.objects.create(name="Kata")
    group = TargetGroup.objects.create(event=event, name="U15", max_age=14)
    group.interests.set([kata])
    occurrence = make_occurrence(event, in_days=5)
    guests.register(event, DATA, [occurrence])  # Interessen zählen bei Gästen nicht
    with pytest.raises(RegistrationError, match="passt leider nicht"):
        guests.register(event, {**DATA, "birth_year": 1990}, [occurrence])
    closed = make_occurrence(event, in_days=5, registration_closes_at=timezone.now() - timedelta(hours=1))
    with pytest.raises(RegistrationError, match="nicht offen"):
        guests.register(event, DATA, [closed])
    assert guests.open_occurrences(event) == [occurrence]


def test_team_adds_guest_immediately(trainer, django_capture_on_commit_callbacks):
    event = Event.objects.create(title="Lehrgang", guests_welcome=True, capacity=0)
    occurrence = make_occurrence(event, in_days=-0.01)  # schon begonnen, Höchstzahl erreicht
    with django_capture_on_commit_callbacks(execute=True):
        guest = guests.register(event, DATA, [occurrence], by=trainer)
    participation = guest.participations.get()
    assert participation.status == ParticipationStatus.REGISTERED
    assert participation.exception_by == trainer
    assert guest.confirmed_at is not None
    assert "Angemeldet: Lehrgang" in mail.outbox[0].subject
    [row] = services.participants(occurrence)
    assert row.guest == guest and row.guardians == []


def test_expire_and_cleanup():
    event = open_event()
    occurrence = make_occurrence(event, in_days=5)
    pending = guests.register(event, DATA, [occurrence])
    assert guests.expire_pending() == 0
    Guest.objects.filter(pk=pending.pk).update(created_at=timezone.now() - timedelta(hours=25))
    assert guests.expire_pending() > 0
    assert not Guest.objects.exists()
    old = make_occurrence(event, in_days=-100)
    kept = guests.register(event, DATA, [occurrence])
    guests.confirm(kept)
    gone = Guest.objects.create(event=event, token="x", consent_at=timezone.now(), **DATA)
    gone.participations.create(occurrence=old, role=role("Teilnehmer"), status="registered")
    guests.cleanup()
    assert list(Guest.objects.all()) == [kept]


def test_cancel_and_promotion_mail_guests(child, parent, django_capture_on_commit_callbacks):
    event = open_event(capacity=1)
    occurrence = make_occurrence(event, in_days=5)
    first = services.register(occurrence, child, parent)
    guest = guests.register(event, DATA, [occurrence])
    guests.confirm(guest)
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        services.unregister(first, parent)
    assert [m.subject.split("] ")[-1] for m in mail.outbox] == ["Nachgerückt: Randori-Lehrgang"]
    with django_capture_on_commit_callbacks(execute=True):
        services.cancel(occurrence)
    assert mail.outbox[-1].to == ["lena@example.org"]
    assert "Abgesagt" in mail.outbox[-1].subject


def test_public_pages(client, django_capture_on_commit_callbacks):
    event = open_event()
    occurrence = make_occurrence(event, in_days=5)
    later = make_occurrence(event, in_days=12)
    url = reverse("guest_register", args=[event.guest_token])
    page = client.get(url)
    assert page.status_code == 200 and "Datenschutzhinweis" in page.content.decode()
    assert client.post(url, form_data(occurrence, website="spam")).status_code == 200
    assert not Guest.objects.exists()
    adult = client.post(url, form_data(occurrence, birth_year="1990", guardian_name=""))
    assert "Fast geschafft" in adult.content.decode()
    child = client.post(url, form_data(occurrence, guardian_name=""))
    assert "Erziehungsberechtigten" in child.content.decode()
    guest = Guest.objects.get()
    page_url = reverse("guest_page", args=[guest.token])
    assert "Bitte bestätige" in client.get(page_url).content.decode()
    client.post(page_url, {"action": "confirm"})
    guest.refresh_from_db()
    assert guest.confirmed_at
    client.post(page_url, {"action": "add", "occurrence": later.pk})
    assert guest.participations.filter(status="registered").count() == 2
    first = guest.participations.get(occurrence=occurrence)
    client.post(page_url, {"action": "cancel", "participation": first.pk})
    first.refresh_from_db()
    assert first.status == ParticipationStatus.CANCELLED
    data = {k: ("" if v is None else v) for k, v in DATA.items()}
    client.post(page_url, {**data, "birth_year": "1990", "phone": "0170 999", "action": "save"})
    guest.refresh_from_db()
    assert guest.phone == "0170 999"
    assert client.get(reverse("guest_page", args=["falsch"])).status_code == 404
    event.guests_welcome = False
    event.save()
    assert client.get(url).status_code == 404


def test_rate_limit(client):
    event = open_event()
    occurrence = make_occurrence(event, in_days=5)
    url = reverse("guest_register", args=[event.guest_token])
    for n in range(10):
        client.post(url, form_data(occurrence, email=f"g{n}@example.org"))
    page = client.post(url, form_data(occurrence, email="zuviel@example.org")).content.decode()
    assert "Zu viele Anmeldungen" in page
    assert Guest.objects.count() == 10


def test_team_page_and_link(client, head, trainer):
    event = open_event()
    occurrence = make_occurrence(event, in_days=5)
    services.set_team(occurrence, services.own_member(trainer), role("Trainer"))
    assert client.login(email=trainer.email, password=PASSWORD)
    data = {k: ("" if v is None else v) for k, v in DATA.items()}
    client.post(reverse("guest_add", args=[occurrence.pk]), data)
    assert Guest.objects.get().participations.get().status == "registered"
    page = client.get(reverse("occurrence_detail", args=[occurrence.pk])).content.decode()
    assert "Lena Gast" in page and "JC Pinneberg" in page
    client.logout()
    assert client.login(email=head.email, password=PASSWORD)
    old = event.guest_token
    assert old in client.get(reverse("event_detail", args=[event.pk])).content.decode()
    client.post(reverse("event_guest_link", args=[event.pk]))
    event.refresh_from_db()
    assert event.guest_token != old
