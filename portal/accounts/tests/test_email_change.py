"""E-Mail-Adresse ändern: gilt erst nach Bestätigung, alte Adresse bekommt einen Hinweis, eigenes Profil zieht mit."""

from __future__ import annotations

from datetime import timedelta
from urllib.parse import urlparse

import pytest
from allauth.account.models import EmailAddress
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from portal.accounts import services
from portal.accounts.models import EmailChange, Role, User
from portal.core.models import AuditEntry
from portal.members.models import LinkKind, Member, MemberLink
from portal.members.tests.conftest import PASSWORD, make_member, make_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def anna() -> User:
    user = make_user("anna@example.org", Role.MEMBER)
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
    member = make_member("Anna", age=30, email="anna@example.org")
    MemberLink.objects.create(user=user, member=member, kind=LinkKind.SELF)
    return user


def login(client, user):
    assert client.login(email=user.email, password=PASSWORD)
    return client


def confirm_link() -> str:
    [message] = [m for m in mail.outbox if m.subject.endswith("Neue E-Mail-Adresse bestätigen")]
    return next(line for line in message.body.splitlines() if "/zugang/e-mail/" in line).strip()


def test_change_needs_confirmation_and_notifies_old_address(client, anna, django_capture_on_commit_callbacks):
    login(client, anna)
    page = client.get(reverse("security")).content.decode()
    assert "Auch in meine Mitgliedsdaten übernehmen" in page
    with django_capture_on_commit_callbacks(execute=True):
        client.post(reverse("email_change"), {"action": "change", "email": "Anna.Neu@Example.org", "sync_member": "on"})
    anna.refresh_from_db()
    assert anna.email == "anna@example.org"  # gilt erst nach Bestätigung
    assert mail.outbox[-1].to == ["anna.neu@example.org"]
    assert "anna.neu@example.org" in client.get(reverse("security")).content.decode()
    path = urlparse(confirm_link()).path
    assert client.get(path).status_code == 200  # bloßes Öffnen ändert nichts
    anna.refresh_from_db()
    assert anna.email == "anna@example.org"
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(path)
    assert response.url == reverse("security")
    anna.refresh_from_db()
    assert anna.email == "anna.neu@example.org"
    assert list(EmailAddress.objects.filter(user=anna).values_list("email", flat=True)) == ["anna.neu@example.org"]
    assert Member.objects.get(first_name="Anna").email == "anna.neu@example.org"
    [notice] = mail.outbox
    assert notice.to == ["anna@example.org"] and "anna.neu@example.org" in notice.body
    assert not EmailChange.objects.exists()
    assert AuditEntry.objects.filter(action="email_changed", user_id=anna.pk).exists()
    assert client.post(path).status_code == 410  # Link nur einmal


def test_member_data_stays_without_checkbox(anna, rf):
    change = services.request_email_change(anna, "neu@example.org", anna, sync_member=False)
    services.confirm_email_change(change, rf.get("/"))
    assert Member.objects.get(first_name="Anna").email == "anna@example.org"


def test_no_checkbox_without_own_profile(client):
    parent = make_user("eltern@example.org")
    login(client, parent)
    assert "Mitgliedsdaten" not in client.get(reverse("security")).content.decode()
    change = services.request_email_change(parent, "neu@example.org", parent, sync_member=True)
    assert not change.sync_member


def test_rejects_taken_same_and_expired(anna, rf):
    make_user("ben@example.org")
    with pytest.raises(services.EmailChangeError, match="anderen Benutzer"):
        services.request_email_change(anna, "BEN@example.org", anna)
    with pytest.raises(services.EmailChangeError, match="aktuelle"):
        services.request_email_change(anna, "anna@example.org", anna)
    change = services.request_email_change(anna, "neu@example.org", anna)
    change.expires_at = timezone.now() - timedelta(minutes=1)
    change.save()
    with pytest.raises(services.EmailChangeError, match="abgelaufen"):
        services.confirm_email_change(change, rf.get("/"))
    assert services.pending_email_change(anna) is None


def test_cancel(client, anna):
    login(client, anna)
    client.post(reverse("email_change"), {"action": "change", "email": "neu@example.org"})
    client.post(reverse("email_change"), {"action": "cancel"})
    assert not EmailChange.objects.exists()


def test_head_changes_email_of_others_with_confirmation(client, anna, django_capture_on_commit_callbacks):
    head = make_user("leitung@example.org", Role.DEPARTMENT_HEAD)
    login(client, head)
    page = client.get(reverse("edit_user", args=[anna.pk])).content.decode()
    assert "Auch in die Mitgliedsdaten von Anna Muster übernehmen" in page
    with django_capture_on_commit_callbacks(execute=True):
        client.post(reverse("user_email_change", args=[anna.pk]), {"action": "change", "email": "neu@example.org"})
    change = EmailChange.objects.get()
    assert change.requested_by == head and not change.sync_member
    assert "Leitung" in mail.outbox[-1].body  # wer die Adresse eingetragen hat
    anna.refresh_from_db()
    assert anna.email == "anna@example.org"
    # Nur die Abteilungsleitung; Administratoren nur durch Administratoren
    admin = make_user("admin@example.org", Role.ADMIN)
    client.post(reverse("user_email_change", args=[admin.pk]), {"action": "change", "email": "x@example.org"})
    assert not EmailChange.objects.filter(user=admin).exists()
    login(client, anna)
    response = client.post(reverse("user_email_change", args=[head.pk]), {"action": "change", "email": "y@example.org"})
    assert response.status_code == 403
