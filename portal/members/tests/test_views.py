"""Seiten der Mitgliederverwaltung und „Meine Daten“: Rechte und Abläufe."""

from decimal import Decimal

import pytest
from django.urls import reverse

from portal.members.models import LinkKind, Member, MemberLink

from .conftest import make_member, make_user

pytestmark = pytest.mark.django_db


def test_member_pages_only_for_department_head(client, head, trainer) -> None:
    ada = make_member("Ada")
    client.force_login(head)
    assert "Ada" in client.get(reverse("member_list")).content.decode()
    assert client.get(reverse("member_detail", args=[ada.pk])).status_code == 200
    client.force_login(trainer)
    for name, args in [("member_list", []), ("member_detail", [ada.pk]), ("member_edit", [ada.pk])]:
        assert client.get(reverse(name, args=args)).status_code == 403, name
    assert reverse("member_list") not in client.get(reverse("home")).content.decode()


def test_member_list_filters(client, head) -> None:
    make_member("Ada")
    make_member("Quirin")
    make_member("Cleo", left_on="2020-01-01")
    client.force_login(head)
    assert "Ada" not in client.get(reverse("member_list"), {"q": "quirin"}).content.decode()
    assert "Cleo" not in client.get(reverse("member_list")).content.decode()
    assert "Cleo" in client.get(reverse("member_list"), {"ehemalige": "1"}).content.decode()


def test_plain_user_has_no_member_list(client) -> None:
    client.force_login(make_user("anna@example.org"))
    assert client.get(reverse("member_list")).status_code == 403
    assert "Mitglieder" not in client.get(reverse("home")).content.decode()


def test_head_creates_and_edits_member(client, head) -> None:
    client.force_login(head)
    data = {"first_name": "Mia", "last_name": "Muster", "birth_date": "2015-03-14", "weight": "32,5"}
    response = client.post(reverse("member_create"), data)
    assert response.status_code == 302
    member = Member.objects.get()
    assert member.weight == Decimal("32.5") and member.member_number is None
    client.post(reverse("member_edit", args=[member.pk]), {**data, "grade": "kyu7", "member_number": " 7 "})
    member.refresh_from_db()
    assert member.grade == "kyu7" and member.member_number == "7"


def test_my_data_single_member_redirects() -> None:
    from django.test import Client

    client = Client()
    user = make_user("ich@example.org")
    me = make_member("Ich", age=30)
    MemberLink.objects.create(user=user, member=me, kind=LinkKind.SELF)
    client.force_login(user)
    response = client.get(reverse("my_data"))
    assert response.status_code == 302 and response.url == reverse("my_member", args=[me.pk])
    assert "Meine Daten" in client.get(reverse("home")).content.decode()


def test_my_data_overview_for_several(client) -> None:
    parent = make_user("eltern@example.org")
    me, child = make_member("Maria", age=40), make_member("Kim", age=8)
    MemberLink.objects.create(user=parent, member=me, kind=LinkKind.SELF)
    MemberLink.objects.create(user=parent, member=child, kind=LinkKind.GUARDIAN)
    client.force_login(parent)
    content = client.get(reverse("my_data")).content.decode()
    assert content.index("Maria") < content.index("Kim")
    assert "Ich" in content and "Kind" in content


def test_my_data_without_links(client) -> None:
    client.force_login(make_user("anna@example.org"))
    assert "noch kein Mitglied verknüpft" in client.get(reverse("my_data")).content.decode()


def test_parent_edits_contact_and_judo_data_only(client) -> None:
    parent = make_user("eltern@example.org")
    child = make_member("Kim", age=8)
    MemberLink.objects.create(user=parent, member=child, kind=LinkKind.GUARDIAN)
    client.force_login(parent)
    response = client.post(
        reverse("my_member_edit", args=[child.pk]),
        {"email": "kim@example.org", "phone": "0170 123", "grade": "kyu8", "weight": "28,4", "first_name": "Hack"},
    )
    assert response.status_code == 302
    child.refresh_from_db()
    assert (child.email, child.phone, child.grade, child.weight) == (
        "kim@example.org",
        "0170 123",
        "kyu8",
        Decimal("28.4"),
    )
    assert child.first_name == "Kim"


def test_foreign_member_not_editable(client) -> None:
    client.force_login(make_user("anna@example.org"))
    other = make_member()
    assert client.get(reverse("my_member", args=[other.pk])).status_code == 403
    assert client.post(reverse("my_member_edit", args=[other.pk]), {"weight": "50"}).status_code == 403


def test_adult_child_no_longer_editable_by_parent(client) -> None:
    parent = make_user("eltern@example.org")
    child = make_member("Kim", age=18)
    MemberLink.objects.create(user=parent, member=child, kind=LinkKind.GUARDIAN)
    client.force_login(parent)
    assert client.get(reverse("my_member", args=[child.pk])).status_code == 403


def test_trainer_with_own_profile_sees_both_entries(client, trainer) -> None:
    MemberLink.objects.create(user=trainer, member=make_member("Tom", age=35), kind=LinkKind.SELF)
    client.force_login(trainer)
    content = client.get(reverse("home")).content.decode()
    assert reverse("my_data") in content and reverse("member_list") not in content
