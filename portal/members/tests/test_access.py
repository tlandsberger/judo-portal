"""Zugänge für Mitglieder und Eltern: Einladung mit Verknüpfung oder direkte Verknüpfung mit Benachrichtigung."""

import pytest
from django.core import mail
from django.urls import reverse

from portal.accounts import services as accounts
from portal.accounts.models import Invitation, Role, User
from portal.members import services
from portal.members.models import LinkKind, MemberLink, PendingLink

from .conftest import make_member, make_user

pytestmark = pytest.mark.django_db


def test_link_kinds_by_age() -> None:
    assert services.link_kinds_for(make_member(age=10)) == [LinkKind.GUARDIAN]
    assert services.link_kinds_for(make_member(age=15)) == [LinkKind.SELF, LinkKind.GUARDIAN]
    assert services.link_kinds_for(make_member(age=30)) == [LinkKind.SELF]


def test_self_link_only_once() -> None:
    member = make_member(age=30)
    services.link(member, make_user("ich@example.org"), LinkKind.SELF)
    assert services.link_kinds_for(member) == []
    with pytest.raises(ValueError):
        services.link(member, make_user("jemand@example.org"), LinkKind.SELF)


def test_user_has_only_one_own_profile() -> None:
    user = make_user("ich@example.org")
    services.link(make_member("A", age=30), user, LinkKind.SELF)
    with pytest.raises(ValueError):
        services.link(make_member("B", age=30), user, LinkKind.SELF)


def test_existing_user_is_linked_directly_and_notified(head, django_capture_on_commit_callbacks) -> None:
    parent = make_user("eltern@example.org")
    child = make_member("Kim", age=8)
    with django_capture_on_commit_callbacks(execute=True):
        result, invitation = services.give_access(child, "Eltern@Example.org", LinkKind.GUARDIAN, invited_by=head)
    assert (result, invitation) == ("linked", None)
    assert MemberLink.objects.get(user=parent, member=child).kind == LinkKind.GUARDIAN
    assert not Invitation.objects.exists()
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["eltern@example.org"]
    assert "Kim Muster" in message.subject and "/meine-daten/" in message.body
    assert not parent.has_role(Role.MEMBER)  # Eltern bekommen keine Rolle


def test_invitation_creates_link_on_accept(client, head, django_capture_on_commit_callbacks) -> None:
    member = make_member("Tim", age=15, email="tim@example.org")
    with django_capture_on_commit_callbacks(execute=True):
        result, invitation = services.give_access(member, "tim@example.org", LinkKind.SELF, invited_by=head)
    assert result == "invited" and invitation is not None
    assert (invitation.first_name, invitation.last_name) == ("Tim", "Muster")
    assert len(mail.outbox) == 1 and "/einladung/" in mail.outbox[0].body
    assert not MemberLink.objects.exists()

    client.post(reverse("accept_invitation", args=[invitation.token]))
    user = User.objects.get(email="tim@example.org")
    assert MemberLink.objects.get(user=user, member=member).kind == LinkKind.SELF
    assert user.has_role(Role.MEMBER)
    assert not PendingLink.objects.exists()


def test_second_invitation_keeps_earlier_pending_links(client, head) -> None:
    first, second = make_member("Kim", age=8), make_member("Lea", age=6)
    services.give_access(first, "eltern@example.org", LinkKind.GUARDIAN, invited_by=head, send=False)
    _, invitation = services.give_access(second, "eltern@example.org", LinkKind.GUARDIAN, invited_by=head, send=False)
    assert Invitation.objects.count() == 1
    assert invitation is not None
    client.post(reverse("accept_invitation", args=[invitation.token]))
    parent = User.objects.get(email="eltern@example.org")
    assert services.own_members(parent) == [first, second]


def test_withdrawn_invitation_drops_pending_links(head) -> None:
    _, invitation = services.give_access(make_member(age=8), "eltern@example.org", LinkKind.GUARDIAN, send=False)
    assert invitation is not None
    invitation.delete()
    assert not PendingLink.objects.exists()


def test_plain_invitation_still_works_without_member(client) -> None:
    invitation = accounts.invite("neu@example.org", send=False)
    client.post(reverse("accept_invitation", args=[invitation.token]))
    assert not MemberLink.objects.exists()


def test_access_view_links_existing_user(client, head) -> None:
    make_user("eltern@example.org")
    child = make_member("Kim", age=8)
    client.force_login(head)
    response = client.post(
        reverse("member_access", args=[child.pk]), {"kind": "guardian", "email": "eltern@example.org", "action": "send"}
    )
    assert response.status_code == 302
    assert MemberLink.objects.filter(member=child, kind=LinkKind.GUARDIAN).exists()


def test_access_view_rejects_self_access_under_14(client, head) -> None:
    child = make_member("Kim", age=10)
    client.force_login(head)
    client.post(reverse("member_access", args=[child.pk]), {"kind": "self", "email": "kim@example.org"})
    assert not Invitation.objects.exists() and not MemberLink.objects.exists()


def test_access_view_link_only(client, head) -> None:
    child = make_member("Kim", age=8)
    client.force_login(head)
    response = client.post(
        reverse("member_access", args=[child.pk]), {"kind": "guardian", "email": "eltern@example.org", "action": "link"}
    )
    assert response.status_code == 200 and "/einladung/" in response.content.decode()
    assert len(mail.outbox) == 0
    assert PendingLink.objects.filter(member=child).exists()


def test_unlink(client, head) -> None:
    member = make_member(age=30)
    member_link = services.link(member, make_user("ich@example.org"), LinkKind.SELF)
    client.force_login(head)
    client.post(reverse("member_unlink", args=[member.pk, member_link.pk]))
    assert not MemberLink.objects.exists()


def test_parents_are_greeted_with_their_children(client, head, django_capture_on_commit_callbacks) -> None:
    """Eltern laden wir ohne Namen ein; Anrede „Liebe Eltern von …“, bis sie ihren Namen ergänzen."""
    kim, lea = make_member("Kim", age=8), make_member("Lea", age=6)
    with django_capture_on_commit_callbacks(execute=True):
        _, invitation = services.give_access(kim, "eltern@example.org", LinkKind.GUARDIAN, invited_by=head)
    assert invitation is not None and (invitation.first_name, invitation.last_name) == ("", "")
    assert mail.outbox[0].body.startswith("Liebe Eltern von Kim,")

    client.post(reverse("accept_invitation", args=[invitation.token]))
    parent = User.objects.get(email="eltern@example.org")
    services.link(lea, parent, LinkKind.GUARDIAN)
    assert parent.greeting == "Liebe Eltern von Kim und Lea"
    client.logout()
    client.force_login(parent)
    home = client.get(reverse("home")).content.decode()
    assert "Liebe Eltern von Kim und Lea" in home and "Wir kennen deinen Namen noch nicht" in home

    parent.first_name = "Sam"
    parent.save()
    assert parent.greeting == "Hallo Sam"
    assert "Wir kennen deinen Namen noch nicht" not in client.get(reverse("home")).content.decode()


def test_greeting_without_name_or_children() -> None:
    assert User.objects.create_user("x@example.org").greeting == "Hallo"
    assert accounts.greeting(invitation=accounts.invite("y@example.org", send=False)) == "Hallo"
