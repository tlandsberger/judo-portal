from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from portal.events.models import Event, TargetGroup, TargetGroupTemplate
from portal.events.services import Match, match_event, match_group, matching_members
from portal.members.models import Interest, Member

pytestmark = pytest.mark.django_db

ON = date(2026, 11, 15)


def member(born: int = 2014, **extra: object) -> Member:
    return Member.objects.create(first_name="Ben", last_name="Muster", birth_date=date(born, 12, 31), **extra)


def test_age_counts_by_birth_year():
    """U13 = Alter bis 12 im Jahr des Termins, auch wenn der Geburtstag erst am 31.12. ist."""
    group = TargetGroupTemplate.objects.create(name="U13", max_age=12)
    assert match_group(group, member(2014), ON) == Match.YES
    assert match_group(group, member(2013), ON) == Match.NO
    assert match_group(group, member(2014), date(2027, 1, 2)) == Match.NO


def test_empty_group_matches_everyone():
    assert match_group(TargetGroupTemplate.objects.create(name="Alle"), member(1980), ON) == Match.YES


def test_gender_and_grade():
    group = TargetGroupTemplate.objects.create(name="Kader m", genders=["m"], min_grade="kyu5", max_grade="kyu1")
    assert match_group(group, member(gender="m", grade="kyu4"), ON) == Match.YES
    assert match_group(group, member(gender="w", grade="kyu4"), ON) == Match.NO
    assert match_group(group, member(gender="m", grade="kyu6"), ON) == Match.NO
    assert match_group(group, member(gender="m", grade="dan1"), ON) == Match.NO
    assert match_group(group, member(gender="m"), ON) == Match.NO


def test_no_grade_counts_as_beginner():
    beginners = TargetGroupTemplate.objects.create(name="Anfänger", max_grade="kyu8")
    assert match_group(beginners, member(), ON) == Match.YES


def test_missing_weight_is_maybe():
    group = TargetGroupTemplate.objects.create(name="bis 40", max_weight=Decimal("40"))
    assert match_group(group, member(), ON) == Match.MAYBE
    assert match_group(group, member(weight=Decimal("40.0")), ON) == Match.YES
    assert match_group(group, member(weight=Decimal("40.1")), ON) == Match.NO


def test_interests_need_one_in_common():
    kata, fight = Interest.objects.create(name="Kata"), Interest.objects.create(name="Wettkampf")
    group = TargetGroupTemplate.objects.create(name="Kata-Gruppe")
    group.interests.set([kata])
    someone = member()
    assert match_group(group, someone, ON) == Match.NO
    someone.interests.set([fight, kata])
    assert match_group(group, someone, ON) == Match.YES


def test_event_matches_best_of_groups():
    event = Event.objects.create(title="Training")
    assert match_event(event, member(1980), ON) == Match.YES  # ohne Zielgruppe: alle
    TargetGroup.objects.create(event=event, name="U11", max_age=10)
    TargetGroup.objects.create(event=event, min_age=18)
    assert match_event(event, member(1980), ON) == Match.YES
    assert match_event(event, member(2014), ON) == Match.NO


def test_matching_members_skips_former():
    group = TargetGroupTemplate.objects.create(name="Alle")
    member()
    member(left_on=date(2020, 1, 1))
    assert len(matching_members(group, ON)) == 1


def test_summary():
    group = TargetGroupTemplate.objects.create(name="U15 m", max_age=14, genders=["m"], min_grade="kyu5")
    assert group.summary == "Alter bis 14 · männlich · ab 5. Kyu"
    assert TargetGroupTemplate.objects.create(name="Alle").summary == "alle Mitglieder"
