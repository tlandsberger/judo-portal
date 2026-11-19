"""Volljährigkeit: Vorankündigung einen Monat vorher, am 18. Geburtstag Verknüpfung lösen, verwaisten Zugang löschen."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.core import mail
from django.urls import reverse

from portal.accounts.models import Role, User
from portal.core.models import AuditEntry
from portal.members.models import LinkKind, Member, MemberLink
from portal.members.tests.conftest import make_user, years_ago
from portal.privacy import services

pytestmark = pytest.mark.django_db


def child_of(user: User, birth_date: date, first_name: str = "Mia") -> Member:
    member = Member.objects.create(first_name=first_name, last_name="Muster", birth_date=birth_date)
    MemberLink.objects.create(user=user, member=member, kind=LinkKind.GUARDIAN)
    return member


@pytest.fixture
def parent() -> User:
    return make_user("eltern@example.org")


def test_notice_one_month_before_with_child_access_link(parent):
    mia = child_of(parent, years_ago(18, days=20))
    child_of(parent, years_ago(18, days=40), first_name="Ben")  # noch zu früh
    assert services.send_adult_notices() == 1
    [message] = mail.outbox
    assert message.subject.endswith("Mia wird 18 Jahre alt: deine Verknüpfung endet")
    assert mia.adult_on().strftime("%d.%m.%Y") in message.body
    assert "Dein Zugang bleibt bestehen" in message.body  # Ben bleibt
    assert reverse("child_access", args=[mia.pk]) in message.body
    assert message.alternatives and "Zugang einrichten" in message.alternatives[0][0]
    assert services.send_adult_notices() == 0  # nur einmal
    assert AuditEntry.objects.filter(action="adult_notice", member_id=mia.pk).exists()


def test_notice_announces_deletion_without_link_if_child_has_access(parent):
    mia = child_of(parent, years_ago(18, days=3))
    MemberLink.objects.create(user=make_user("mia@example.org"), member=mia, kind=LinkKind.SELF)
    services.send_adult_notices()
    [message] = mail.outbox
    assert "wird an diesem Tag auch dein Zugang gelöscht" in message.body
    assert "/eigener-zugang/" not in message.body


def test_release_deletes_orphaned_user_with_one_mail(parent, run_on_commit):
    mia = child_of(parent, years_ago(18))
    MemberLink.objects.create(user=make_user("mia@example.org"), member=mia, kind=LinkKind.SELF)
    assert run_on_commit(services.release_adult_children) == 1
    assert not User.objects.filter(email="eltern@example.org").exists()
    assert User.objects.filter(email="mia@example.org").exists()  # das eigene Profil bleibt
    [message] = mail.outbox
    assert message.to == ["eltern@example.org"]
    assert "Mia Muster ist jetzt volljährig" in message.body and "auch dein Zugang gelöscht" in message.body
    assert AuditEntry.objects.filter(action="unlink", member_id=mia.pk).exists()


def test_release_keeps_user_with_other_child_or_function(parent, run_on_commit):
    child_of(parent, years_ago(18))
    child_of(parent, years_ago(12), first_name="Ben")
    trainer = make_user("trainer@example.org", Role.TRAINER)
    child_of(trainer, years_ago(19), first_name="Lea")
    assert run_on_commit(services.release_adult_children) == 2
    assert User.objects.filter(email__in=["eltern@example.org", "trainer@example.org"]).count() == 2
    assert MemberLink.objects.filter(user=parent).count() == 1
    assert not MemberLink.objects.filter(user=trainer).exists()
    assert len(mail.outbox) == 2
    assert all("Dein Zugang bleibt bestehen" in m.body for m in mail.outbox)


def test_not_released_before_birthday(parent):
    child_of(parent, years_ago(18, days=1))
    assert services.release_adult_children() == 0
    assert MemberLink.objects.filter(user=parent).exists()


def test_leap_day_child_becomes_adult_on_first_of_march(parent):
    member = child_of(parent, date(2008, 2, 29))
    assert member.adult_on() == date(2026, 3, 1)
    assert member.age(date(2026, 2, 28)) == 17
    assert services.send_adult_notices(date(2026, 2, 1)) == 1
    assert services.release_adult_children(date(2026, 2, 28)) == 0
    assert services.release_adult_children(date(2026, 3, 1)) == 1


def test_daily_job_runs_both(parent, run_on_commit):
    child_of(parent, years_ago(18) - timedelta(days=1))
    run_on_commit(services.run_daily)
    assert not User.objects.filter(email="eltern@example.org").exists()
