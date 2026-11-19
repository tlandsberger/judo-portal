from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from portal.accounts.models import Role, User
from portal.events import services
from portal.events.models import Event, EventType, Occurrence, ParticipantRole
from portal.members.models import LinkKind, Member, MemberLink
from portal.members.tests.conftest import PASSWORD, make_member, make_user, years_ago

__all__ = [
    "PASSWORD",
    "event_type",
    "make_member",
    "make_occurrence",
    "make_trainer",
    "make_user",
    "rates_not_required",
    "rates_required",
    "role",
    "years_ago",
]


def role(name: str) -> ParticipantRole:
    """Rollen aus der Migration: Teilnehmer, Trainer, Co-Trainer, Prüfer, Betreuer."""
    return ParticipantRole.objects.get(name=name)


def event_type(name: str) -> EventType:
    """Arten aus der Migration: Training, Wettkampf, Lehrgang, Prüfung, Sonstiges."""
    return EventType.objects.get(name=name)


def make_trainer(email: str = "anna@example.org", first_name: str = "Anna") -> User:
    """Übungsleiter mit eigenem Mitgliedsprofil (Voraussetzung für Team-Rollen)."""
    user = make_user(email, Role.TRAINER)
    member = make_member(first_name, last_name="Trainer", age=35)
    MemberLink.objects.create(user=user, member=member, kind=LinkKind.SELF)
    return user


def make_occurrence(
    event: Event | None = None, *, in_days: float = 3, hours: float = 1.5, **extra: object
) -> Occurrence:
    event = event or Event.objects.create(title="Training")
    starts = timezone.now().replace(microsecond=0) + timedelta(days=in_days)
    return Occurrence.objects.create(event=event, starts_at=starts, ends_at=starts + timedelta(hours=hours), **extra)


@pytest.fixture(autouse=True)
def rates_not_required(request, monkeypatch):
    """Die meisten Tests prüfen Termine, nicht Stundensätze: ohne ``rates_required`` ist die Prüfung aus ``billing``
    (Stundensatz für abrechnungsrelevante Rollen) abgeschaltet."""
    if "rates_required" not in request.fixturenames:
        monkeypatch.setattr(services, "_role_checks", [])


@pytest.fixture
def rates_required() -> None:
    """Prüfungen anderer Apps für Rollen (Stundensatz) gelten wie im Betrieb."""


@pytest.fixture
def head(db) -> User:
    return make_user("leitung@example.org", Role.DEPARTMENT_HEAD)


@pytest.fixture
def trainer(db) -> User:
    return make_trainer()


@pytest.fixture
def parent(db) -> User:
    return make_user("eltern@example.org")


@pytest.fixture
def child(parent) -> Member:
    member = make_member("Mia", age=10, gender="w")
    MemberLink.objects.create(user=parent, member=member, kind=LinkKind.GUARDIAN)
    return member
