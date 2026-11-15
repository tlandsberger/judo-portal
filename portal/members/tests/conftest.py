from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.utils import timezone

from portal.accounts.models import Role, User
from portal.members.models import Member


def years_ago(years: int, days: int = 0) -> date:
    """Geburtsdatum für ein Alter; days > 0 heißt: der Geburtstag ist erst in ``days`` Tagen."""
    today = timezone.localdate()
    if (today.month, today.day) == (2, 29):
        today -= timedelta(days=1)
    return today.replace(year=today.year - years) + timedelta(days=days)


PASSWORD = "Sicher-12345!"


def make_user(email: str, *roles: Role) -> User:
    user = User.objects.create_user(email, password=PASSWORD, first_name=email.split("@")[0].title())
    if roles:
        user.set_roles(list(roles))
    return user


def make_member(first_name: str = "Mia", last_name: str = "Muster", age: int = 10, **extra: object) -> Member:
    return Member.objects.create(first_name=first_name, last_name=last_name, birth_date=years_ago(age), **extra)


@pytest.fixture
def head(db) -> User:
    return make_user("leitung@example.org", Role.DEPARTMENT_HEAD)


@pytest.fixture
def trainer(db) -> User:
    return make_user("trainer@example.org", Role.TRAINER)
