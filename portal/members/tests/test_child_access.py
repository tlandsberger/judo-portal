"""Eigener Zugang für Kinder ab 14: Eltern laden ein, Banner auf der Startseite, Mail zum 14. Geburtstag."""

from __future__ import annotations

import pytest
from django.core import mail
from django.urls import reverse

from portal.accounts.models import Invitation, User
from portal.core.models import AuditEntry
from portal.members import child_access
from portal.members.models import AccessOffer, LinkKind, Member, MemberLink, PendingLink

from .conftest import PASSWORD, make_user, years_ago

pytestmark = pytest.mark.django_db


@pytest.fixture
def parent() -> User:
    return make_user("eltern@example.org")


def child_of(parent: User, age: int = 14, days: int = 0, **extra: object) -> Member:
    member = Member.objects.create(first_name="Mia", last_name="Muster", birth_date=years_ago(age, days), **extra)
    MemberLink.objects.create(user=parent, member=member, kind=LinkKind.GUARDIAN)
    return member


def login(client, user):
    assert client.login(email=user.email, password=PASSWORD)
    return client


def test_banner_only_for_children_from_14_without_access(client, parent):
    young = child_of(parent, age=13)
    login(client, parent)
    assert "eigenen Zugang bekommen" not in client.get(reverse("home")).content.decode()
    mia = child_of(parent, age=15)
    page = client.get(reverse("home")).content.decode()
    assert "Mia ist 15 Jahre alt und kann einen eigenen Zugang bekommen" in page
    assert reverse("child_access", args=[mia.pk]) in page
    assert reverse("child_access", args=[young.pk]) not in page
    # Kein Banner für das eigene Profil oder für 18-Jährige
    assert child_access.banner_children(make_user("x@example.org")) == []
    child_of(parent, age=18)
    assert child_access.banner_children(parent) == [mia]


def test_not_now_hides_banner_but_page_stays(client, parent):
    mia = child_of(parent)
    login(client, parent)
    response = client.post(reverse("child_access_dismiss", args=[mia.pk]))
    assert response.url == reverse("home")
    assert "eigenen Zugang bekommen" not in client.get(reverse("home")).content.decode()
    assert "Zugang einrichten" in client.get(reverse("my_member", args=[mia.pk])).content.decode()
    assert client.get(reverse("child_access", args=[mia.pk])).status_code == 200


def test_parent_invites_child(client, parent, django_capture_on_commit_callbacks):
    mia = child_of(parent, email="eltern@example.org")
    login(client, parent)
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            reverse("child_access", args=[mia.pk]), {"email": "Mia@Example.org", "sync_member": "on"}
        )
    assert response.url == reverse("my_member", args=[mia.pk])
    invitation = Invitation.objects.get(email="mia@example.org")
    assert invitation.invited_by == parent and invitation.first_name == "Mia"
    assert PendingLink.objects.get(invitation=invitation).kind == LinkKind.SELF
    assert mail.outbox[-1].to == ["mia@example.org"]
    mia.refresh_from_db()
    assert mia.email == "mia@example.org"
    assert AuditEntry.objects.filter(action="invite", member_id=mia.pk).exists()
    # Banner weg, an der Seite des Kindes steht die offene Einladung
    assert "eigenen Zugang bekommen" not in client.get(reverse("home")).content.decode()
    assert (
        "Die Einladung an mia@example.org ist verschickt"
        in client.get(reverse("my_member", args=[mia.pk])).content.decode()
    )


def test_new_invitation_replaces_earlier_one(parent):
    mia = child_of(parent)
    child_access.invite_child(parent, mia, "alt@example.org")
    child_access.invite_child(parent, mia, "neu@example.org", sync_member=False)
    assert not Invitation.objects.filter(email="alt@example.org").exists()
    assert child_access.pending_invitation(mia).email == "neu@example.org"
    mia.refresh_from_db()
    assert mia.email == ""


def test_rejects_existing_user_and_strangers(client, parent):
    mia = child_of(parent)
    with pytest.raises(child_access.ChildAccessError, match="schon einen Benutzer"):
        child_access.invite_child(parent, mia, "ELTERN@example.org")
    with pytest.raises(child_access.ChildAccessError):
        child_access.invite_child(make_user("fremd@example.org"), mia, "mia@example.org")
    young = child_of(parent, age=13)
    with pytest.raises(child_access.ChildAccessError):
        child_access.invite_child(parent, young, "mia@example.org")
    login(client, parent)
    assert client.get(reverse("child_access", args=[young.pk])).status_code == 403
    login(client, make_user("fremd2@example.org"))
    assert client.get(reverse("child_access", args=[mia.pk])).status_code == 403
    assert client.post(reverse("child_access_dismiss", args=[mia.pk])).status_code == 403


def test_child_with_own_access(client, parent):
    mia = child_of(parent)
    MemberLink.objects.create(user=make_user("mia@example.org"), member=mia, kind=LinkKind.SELF)
    assert child_access.banner_children(parent) == []
    with pytest.raises(child_access.ChildAccessError):
        child_access.invite_child(parent, mia, "mia2@example.org")
    login(client, parent)
    assert (
        "Mia hat einen eigenen Zugang (mia@example.org)"
        in client.get(reverse("my_member", args=[mia.pk])).content.decode()
    )


def test_birthday_mail_once_and_only_for_recent_birthdays(parent):
    second = make_user("zweiter@example.org")
    mia = child_of(parent, age=14, days=-2)  # vor zwei Tagen 14 geworden
    MemberLink.objects.create(user=second, member=mia, kind=LinkKind.GUARDIAN)
    child_of(parent, age=15)  # schon länger 14: nur Banner
    child_of(parent, age=14, days=1)  # morgen 14
    assert child_access.notify_birthdays() == 2
    assert sorted(m.to[0] for m in mail.outbox) == ["eltern@example.org", "zweiter@example.org"]
    message = mail.outbox[0]
    assert "Mia kann jetzt einen eigenen Zugang bekommen" in message.subject
    assert reverse("child_access", args=[mia.pk]) in message.body
    assert message.alternatives and "Zugang einrichten" in message.alternatives[0][0]
    assert child_access.notify_birthdays() == 0  # nur einmal
    assert AccessOffer.objects.filter(member=mia, notified_at__isnull=False).count() == 2


def test_no_birthday_mail_with_access_or_invitation(parent):
    mia = child_of(parent, age=14)
    child_access.invite_child(parent, mia, "mia@example.org")
    mail.outbox.clear()
    assert child_access.notify_birthdays() == 0


def test_offers_in_privacy_export(parent):
    from portal.privacy.services import export_user

    mia = child_of(parent)
    child_access.dismiss(parent, mia)
    [row] = export_user(parent)["Hinweise auf eigenen Zugang für Kinder"]
    assert row["Mitglied"] == "Mia Muster" and row["Ausgeblendet"]


def test_accepting_links_child(parent):
    mia = child_of(parent)
    invitation = child_access.invite_child(parent, mia, "mia@example.org")
    user = User.objects.create_user("mia@example.org")
    from portal.members.services import complete_pending_links

    complete_pending_links(invitation, user)
    assert MemberLink.objects.filter(user=user, member=mia, kind=LinkKind.SELF).exists()
