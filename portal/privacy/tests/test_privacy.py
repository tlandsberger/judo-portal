"""Auskunft und Löschen (ADR 0015)."""

from __future__ import annotations

import json
from datetime import timedelta

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from portal.accounts.models import Role, User
from portal.billing import services as billing
from portal.billing.models import Claim
from portal.core.models import AuditEntry
from portal.events import services as events
from portal.events.models import Participation
from portal.members.models import LinkKind, Member, MemberLink
from portal.privacy import services

from .conftest import make_member, make_shift, make_user, month_ago, set_rate

pytestmark = pytest.mark.django_db


def test_export_contains_own_and_children_only(client, parent, child):
    adult_child = make_member("Lena", age=19)
    MemberLink.objects.create(user=parent, member=adult_child, kind=LinkKind.GUARDIAN)
    make_member("Fremd")
    data = services.export(parent)
    assert list(data["Mitglieder"]) == ["Mia Muster"]
    assert data["Benutzer"]["E-Mail"] == parent.email
    client.force_login(parent)
    page = client.get(reverse("my_privacy"))
    assert "Mia Muster" in page.content.decode() and "Lena" not in page.content.decode()
    download = client.get(reverse("my_privacy"), {"format": "json"})
    assert download["Content-Type"].startswith("application/json")
    assert json.loads(download.content)["Mitglieder"]["Mia Muster"]["Stammdaten"]["Vorname"] == "Mia"


def test_member_export_only_for_head(client, head, parent, child):
    client.force_login(parent)
    assert client.get(reverse("member_export", args=[child.pk])).status_code == 403
    client.force_login(head)
    assert json.loads(client.get(reverse("member_export", args=[child.pk])).content)["Stammdaten"]["Vorname"] == "Mia"


def test_delete_member_with_everything(trainer, head, run_on_commit):
    member = events.own_member(trainer)
    member.member_number = "2001"
    member.save()
    set_rate(trainer)
    make_shift(trainer, month_ago() + timedelta(days=2))
    billing.submit(member, month_ago(), trainer)
    member_id = member.pk
    run_on_commit(services.delete_member, member, head, services.REASON_REQUEST)
    assert not Member.objects.exists() and not Participation.objects.exists() and not Claim.objects.exists()
    assert User.objects.filter(pk=trainer.pk).exists()  # Übungsleiter bleibt als Benutzer
    assert AuditEntry.objects.filter(member_id=member_id).count() == 0
    assert AuditEntry.objects.filter(action="member_deleted").get().summary == "Mitglied Nr. 2001 gelöscht (auf Wunsch)"


def test_orphaned_parent_is_deleted_with_mail(parent, child, head, run_on_commit):
    second_parent = make_user("zweiter@example.org")
    MemberLink.objects.create(user=second_parent, member=child, kind=LinkKind.GUARDIAN)
    sibling = make_member("Tom")
    MemberLink.objects.create(user=second_parent, member=sibling, kind=LinkKind.GUARDIAN)
    preview = services.preview_deletion(child)
    assert preview.users_deleted == [parent]
    run_on_commit(services.delete_member, child, head, services.REASON_REQUEST)
    assert not User.objects.filter(pk=parent.pk).exists()
    assert User.objects.filter(pk=second_parent.pk).exists()
    assert [m.to for m in mail.outbox] == [[parent.email]]
    assert "gelöscht" in mail.outbox[0].subject


def test_member_role_does_not_keep_user(head, run_on_commit):
    user = make_user("ich@example.org", Role.MEMBER)
    member = make_member("Ich", age=30)
    MemberLink.objects.create(user=user, member=member, kind=LinkKind.SELF)
    run_on_commit(services.delete_member, member, head, services.REASON_REQUEST)
    assert not User.objects.filter(pk=user.pk).exists()


def test_notice_and_automatic_deletion(parent, child, run_on_commit):
    today = timezone.localdate()
    child.left_on = today
    child.save()
    assert services.deletion_date(child) == services._add_months(today, 3)
    run_on_commit(services.run_daily, today)
    run_on_commit(services.run_daily, today + timedelta(days=1))
    assert len(mail.outbox) == 1 and "Austritt" in mail.outbox[0].subject
    assert "Mia" in mail.outbox[0].body
    # Austritt geändert: der Hinweis geht erneut
    child.refresh_from_db()
    child.left_on = today - timedelta(days=1)
    child.save()
    run_on_commit(services.send_deletion_notices, today)
    assert len(mail.outbox) == 2
    # Drei Monate später: gelöscht, der Elternteil mit
    run_on_commit(services.run_daily, services._add_months(today, 3))
    assert not Member.objects.exists() and not User.objects.filter(pk=parent.pk).exists()


def test_notice_for_later_entered_exit(child, run_on_commit):
    child.left_on = timezone.localdate() - timedelta(days=20)
    child.save()
    run_on_commit(services.run_daily)
    assert len(mail.outbox) == 1


def test_deleted_soon_list(client, head):
    today = timezone.localdate()
    soon = make_member("Bald", left_on=services._add_months(today, -3) + timedelta(days=10))
    make_member("Später", left_on=today)
    assert [member for member, _ in services.deleted_soon()] == [soon]
    client.force_login(head)
    assert "Wird in den nächsten 30 Tagen gelöscht" in client.get(reverse("member_list")).content.decode()


def test_delete_page_needs_confirmation(client, head, parent, child):
    url = reverse("member_delete", args=[child.pk])
    client.force_login(parent)
    assert client.get(url).status_code == 403
    client.force_login(head)
    page = client.get(url).content.decode()
    assert "Endgültig löschen" in page and parent.display_name in page
    client.post(url, {})
    assert Member.objects.filter(pk=child.pk).exists()
    client.post(url, {"confirm": "on"})
    assert not Member.objects.filter(pk=child.pk).exists()


def test_guest_cleanup_forgets_audit():
    from portal.core import audit
    from portal.events import guests
    from portal.events.models import Event, Guest

    event = Event.objects.create(title="Lehrgang", guests_welcome=True)
    guest = Guest.objects.create(
        event=event,
        first_name="Lena",
        last_name="Gast",
        birth_year=2000,
        gender="w",
        email="l@example.org",
        phone="1",
        consent_at=timezone.now(),
        token="t1",
    )
    audit.log(None, audit.Area.EVENTS, "guest_register", "Gast Lena Gast angemeldet", guest=guest)
    Guest.objects.filter(pk=guest.pk).update(created_at=timezone.now() - timedelta(days=2))
    assert guests.expire_pending() == 1
    assert not AuditEntry.objects.filter(guest_id=guest.pk).exists()
    assert AuditEntry.objects.get(action="guests_deleted").summary.startswith("1 Gäste gelöscht")
