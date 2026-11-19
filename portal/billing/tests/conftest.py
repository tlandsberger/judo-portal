from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from portal.accounts.models import User
from portal.billing import services
from portal.billing.models import Rate
from portal.events import services as events
from portal.events.models import Event, Occurrence, Participation
from portal.events.tests.conftest import (
    child,
    head,
    make_member,
    make_trainer,
    make_user,
    parent,
    rates_not_required,
    rates_required,
    role,
    trainer,
)

__all__ = [
    "child",
    "head",
    "make_member",
    "make_trainer",
    "make_user",
    "parent",
    "rates_not_required",
    "rates_required",
    "role",
    "trainer",
]


def month_ago(count: int = 1) -> date:
    return services.add_months(services.first_of_month(timezone.localdate()), -count)


def make_shift(
    user: User, day: date, *, role_name: str = "Trainer", hours: float = 1.5, confirm: bool = True, minutes: int = 0
) -> Participation:
    """Termin am ``day`` um 18 Uhr mit dem Übungsleiter im Team, auf Wunsch bestätigt."""
    starts = timezone.make_aware(datetime.combine(day, time(18)))
    event = Event.objects.create(title=f"Training {day:%d.%m.}")
    occurrence = Occurrence.objects.create(event=event, starts_at=starts, ends_at=starts + timedelta(hours=hours))
    member = events.own_member(user)
    assert member is not None
    participation = events.set_team(occurrence, member, role(role_name))
    if confirm:
        events.confirm(participation, minutes or None)
    return participation


def set_rate(user: User, role_name: str = "Trainer", value: str = "15.00", valid_from: date | None = None) -> Rate:
    member = events.own_member(user)
    return Rate.objects.create(
        member=member, role=role(role_name), hourly_rate=Decimal(value), valid_from=valid_from or date(2020, 1, 1)
    )


@pytest.fixture
def other_trainer(db) -> User:
    return make_trainer("ben@example.org", "Ben")


@pytest.fixture
def run_on_commit(django_capture_on_commit_callbacks):
    """Führt eine Funktion aus und danach die Callbacks nach dem Commit (Benachrichtigungen)."""

    def runner(func, *args, **kwargs):
        with django_capture_on_commit_callbacks(execute=True):
            return func(*args, **kwargs)

    return runner
