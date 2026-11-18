"""Änderungsprotokoll: Einträge aus allen Bereichen, Aufbewahrung (ADR 0015)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from portal.core import audit
from portal.core.models import AuditEntry
from portal.events import services as events
from portal.members import csv_import
from portal.members.tests.conftest import PASSWORD

from .conftest import make_member, make_shift, month_ago, set_rate

pytestmark = pytest.mark.django_db


def test_member_edit_logs_diff(client, head):
    member = make_member("Mia", phone="")
    client.force_login(head)
    data = {
        "first_name": "Mia",
        "last_name": "Muster",
        "birth_date": member.birth_date.isoformat(),
        "phone": "040 123",
        "grade": "",
        "gender": "",
    }
    client.post(reverse("member_edit", args=[member.pk]), data)
    entry = AuditEntry.objects.get(action="update")
    assert entry.member_id == member.pk and entry.actor == head
    assert entry.changes["Telefon"] == ["", "040 123"]
    assert "Letzte Änderungen" in client.get(reverse("member_detail", args=[member.pk])).content.decode()


def test_csv_import_logs_create(head):
    csv_import.apply("Mitgliedsnummer;Vorname;Nachname;Geburtsdatum\n9001;Ole;Neu;01.02.2010\n", by=head)
    assert AuditEntry.objects.get(action="create").summary == "Ole Neu angelegt (CSV-Import)"


def test_csv_import_never_creates_departed_members(head):
    yesterday = (timezone.localdate() - timedelta(days=1)).strftime("%d.%m.%Y")
    tomorrow = (timezone.localdate() + timedelta(days=1)).strftime("%d.%m.%Y")
    text = (
        "Mitgliedsnummer;Vorname;Nachname;Geburtsdatum;Austritt\n"
        f"9001;Alt;Weg;01.02.2010;{yesterday}\n9002;Bald;Weg;01.02.2010;{tomorrow}\n"
    )
    preview = csv_import.preview(text)
    assert [row.status for row in preview.rows] == ["left", "new"]
    csv_import.apply(text, by=head)
    from portal.members.models import Member

    assert list(Member.objects.values_list("first_name", flat=True)) == ["Bald"]
    # Ein bestehendes Mitglied bekommt den Austritt trotzdem
    csv_import.apply(f"Mitgliedsnummer;Vorname;Nachname;Geburtsdatum;Austritt\n9002;Bald;Weg;01.02.2010;{yesterday}\n")
    assert Member.objects.get().left_on == timezone.localdate() - timedelta(days=1)


def test_login_and_settings_are_logged(client, parent):
    client.force_login(parent)
    client.post(
        reverse("account_change_password"),
        {"oldpassword": PASSWORD, "password1": "Neu-Sicher-987!", "password2": "Neu-Sicher-987!"},
    )
    client.post(reverse("security"), {"phone": "0170 1"})
    actions = set(AuditEntry.objects.filter(user_id=parent.pk).values_list("action", flat=True))
    assert {"password_changed", "profile"} <= actions


def test_events_and_billing_are_logged(trainer, head):
    set_rate(trainer)
    shift = make_shift(trainer, month_ago() + timedelta(days=2))
    events.confirm(shift, 60, by=trainer)
    actions = list(AuditEntry.objects.order_by("pk").values_list("action", flat=True))
    assert actions[:3] == ["team", "confirm", "confirm_update"]
    entry = AuditEntry.objects.get(action="confirm_update")
    assert entry.changes == {"Minuten": [90, 60]} and entry.actor == trainer


def test_cleanup_after_one_year():
    old = audit.log(None, audit.Area.MEMBERS, "x", "alt")
    AuditEntry.objects.filter(pk=old.pk).update(at=timezone.now() - timedelta(days=366))
    audit.log(None, audit.Area.MEMBERS, "y", "neu")
    assert audit.cleanup() == 1
    assert list(AuditEntry.objects.values_list("summary", flat=True)) == ["neu"]


def test_audit_page_only_for_head(client, head, parent):
    audit.log(head, audit.Area.MEMBERS, "x", "Testeintrag")
    client.force_login(parent)
    assert client.get(reverse("audit_list")).status_code == 403
    client.force_login(head)
    page = client.get(reverse("audit_list"), {"area": "members"}).content.decode()
    assert "Testeintrag" in page
