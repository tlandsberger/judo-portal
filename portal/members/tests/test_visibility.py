"""Wer welche Mitglieder sieht und ändern darf (ADR 0003)."""

import pytest

from portal.members import services
from portal.members.models import LinkKind, MemberLink

from .conftest import make_member, make_user, years_ago

pytestmark = pytest.mark.django_db


def test_department_head_sees_all(head) -> None:
    a, b = make_member("Ada"), make_member("Ben")
    assert set(services.visible_members(head)) == {a, b}
    assert services.can_manage_members(head)


def test_trainer_sees_no_members(trainer) -> None:
    member = make_member("Ada")
    assert not services.visible_members(trainer).exists()
    assert not services.can_view(trainer, member)
    assert not services.can_manage_members(trainer)


def test_plain_user_sees_nothing_without_links(db) -> None:
    user = make_user("anna@example.org")
    make_member()
    assert not services.visible_members(user).exists()


def test_guardian_sees_children_until_18() -> None:
    parent = make_user("eltern@example.org")
    child = make_member("Kim", age=17)
    adult = make_member("Lou", age=18)
    for member in (child, adult):
        MemberLink.objects.create(user=parent, member=member, kind=LinkKind.GUARDIAN)
    assert services.own_members(parent) == [child]
    assert services.can_view(parent, child) and services.can_self_edit(parent, child)
    assert not services.can_view(parent, adult) and not services.can_self_edit(parent, adult)


def test_guardian_link_ends_on_18th_birthday() -> None:
    parent = make_user("eltern@example.org")
    member = make_member("Kim")
    member.birth_date = years_ago(18, days=1)  # morgen 18
    member.save()
    member_link = MemberLink.objects.create(user=parent, member=member, kind=LinkKind.GUARDIAN)
    assert member_link.is_effective()
    member.birth_date = years_ago(18)  # heute 18
    member.save()
    member_link.refresh_from_db()
    assert not member_link.is_effective()


def test_two_parents_each_see_child_but_not_each_other() -> None:
    mother, father = make_user("mutter@example.org"), make_user("vater@example.org")
    child = make_member("Kim", age=8)
    mother_profile = make_member("Maria", age=40)
    MemberLink.objects.create(user=mother, member=mother_profile, kind=LinkKind.SELF)
    for parent in (mother, father):
        MemberLink.objects.create(user=parent, member=child, kind=LinkKind.GUARDIAN)
    assert services.own_members(mother) == [mother_profile, child]
    assert services.own_members(father) == [child]
    assert not services.can_view(father, mother_profile)


def test_own_profile_first_then_children_by_age() -> None:
    parent = make_user("eltern@example.org")
    young, old = make_member("Jung", age=6), make_member("Alt", age=12)
    me = make_member("Ich", age=40)
    MemberLink.objects.create(user=parent, member=young, kind=LinkKind.GUARDIAN)
    MemberLink.objects.create(user=parent, member=me, kind=LinkKind.SELF)
    MemberLink.objects.create(user=parent, member=old, kind=LinkKind.GUARDIAN)
    assert services.own_members(parent) == [me, old, young]


def test_inactive_user_sees_nothing() -> None:
    user = make_user("anna@example.org")
    MemberLink.objects.create(user=user, member=make_member(age=30), kind=LinkKind.SELF)
    user.is_active = False
    user.save()
    assert services.own_members(user) == []
