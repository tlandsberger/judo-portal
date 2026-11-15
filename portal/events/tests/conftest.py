from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from portal.accounts.models import Role, User
from portal.events.models import Event, Occurrence
from portal.members.models import LinkKind, Member, MemberLink
from portal.members.tests.conftest import PASSWORD, make_member, make_user, years_ago

__all__ = ["PASSWORD", "make_member", "make_occurrence", "make_user", "years_ago"]


def make_occurrence(
    event: Event | None = None, *, in_days: float = 3, hours: float = 1.5, **extra: object
) -> Occurrence:
    event = event or Event.objects.create(title="Training")
    starts = timezone.now().replace(microsecond=0) + timedelta(days=in_days)
    return Occurrence.objects.create(event=event, starts_at=starts, ends_at=starts + timedelta(hours=hours), **extra)


@pytest.fixture
def head(db) -> User:
    return make_user("leitung@example.org", Role.DEPARTMENT_HEAD)


@pytest.fixture
def trainer(db) -> User:
    return make_user("anna@example.org", Role.TRAINER)


@pytest.fixture
def parent(db) -> User:
    return make_user("eltern@example.org")


@pytest.fixture
def child(parent) -> Member:
    member = make_member("Mia", age=10, gender="w")
    MemberLink.objects.create(user=parent, member=member, kind=LinkKind.GUARDIAN)
    return member
