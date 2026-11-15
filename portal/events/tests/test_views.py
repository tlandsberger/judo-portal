from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from portal.accounts.models import Role
from portal.events.models import Event, Registration, RegistrationStatus, StaffFunction, Staffing, TargetGroup
from portal.members.models import Interest

from .conftest import PASSWORD, make_member, make_occurrence, make_user

pytestmark = pytest.mark.django_db


def login(client, user):
    assert client.login(email=user.email, password=PASSWORD)
    return client


def test_agenda_quick_registration(client, parent, child):
    occurrence = make_occurrence()
    login(client, parent)
    page = client.get(reverse("agenda"))
    assert page.status_code == 200
    assert "Training" in page.content.decode()
    client.post(reverse("register", args=[occurrence.pk, child.pk]), {"next": reverse("agenda")})
    assert Registration.objects.get().status == RegistrationStatus.REGISTERED
    client.post(reverse("unregister", args=[occurrence.pk, child.pk]))
    assert Registration.objects.get().status == RegistrationStatus.CANCELLED


def test_register_form_with_weight(client, parent, child):
    occurrence = make_occurrence(Event.objects.create(title="Wettkampf", kind="competition", weight_required=True))
    login(client, parent)
    page = client.get(reverse("register", args=[occurrence.pk, child.pk]))
    assert "Gewicht" in page.content.decode()
    client.post(reverse("register", args=[occurrence.pk, child.pk]))  # ohne Formular: nicht angemeldet
    assert not Registration.objects.exists()
    client.post(reverse("register", args=[occurrence.pk, child.pk]), {"form": "1", "weight": "31,5", "note": ""})
    child.refresh_from_db()
    assert str(child.weight) == "31.5"
    assert Registration.objects.get().weight == child.weight


def test_cannot_register_foreign_member(client, parent):
    stranger = make_member("Ole")
    occurrence = make_occurrence()
    login(client, parent)
    assert client.post(reverse("register", args=[occurrence.pk, stranger.pk])).status_code == 403


def test_participants_only_for_accompanying_trainer(client, trainer, parent, child):
    other = make_user("tom@example.org", Role.TRAINER)
    occurrence = make_occurrence()
    Staffing.objects.create(occurrence=occurrence, user=trainer, function=StaffFunction.TRAINER)
    Registration.objects.create(occurrence=occurrence, member=child, status=RegistrationStatus.REGISTERED)
    page = login(client, trainer).get(reverse("occurrence_detail", args=[occurrence.pk])).content.decode()
    assert "Teilnehmer (1)" in page and parent.email in page
    client.logout()
    page = login(client, other).get(reverse("occurrence_detail", args=[occurrence.pk])).content.decode()
    assert "Teilnehmer" not in page and parent.email not in page
    assert client.get(reverse("participant_add", args=[occurrence.pk])).status_code == 403
    assert client.get(reverse("member_list")).status_code == 403


def test_trainer_adds_self_and_exception(client, trainer, child):
    occurrence = make_occurrence(Event.objects.create(title="Kader"))
    occurrence.event.target_groups.set([TargetGroup.objects.create(name="Erwachsene", min_age=18)])
    login(client, trainer)
    client.post(reverse("occurrence_staff", args=[occurrence.pk]), {"function": "trainer"})
    assert occurrence.staffings.get().function == StaffFunction.TRAINER
    results = client.get(reverse("participant_add", args=[occurrence.pk]), {"q": "Mi"}).content.decode()
    assert child.display_name in results
    client.post(reverse("participant_add", args=[occurrence.pk]), {"member": child.pk})
    assert Registration.objects.get().exception_by == trainer


def test_trainer_changes_function_of_others(client, trainer):
    other = make_user("tom@example.org", Role.TRAINER)
    occurrence = make_occurrence()
    Staffing.objects.create(occurrence=occurrence, user=trainer, function=StaffFunction.CO_TRAINER)
    Staffing.objects.create(occurrence=occurrence, user=other, function=StaffFunction.TRAINER)
    login(client, trainer)
    client.post(reverse("occurrence_staff", args=[occurrence.pk]), {"user": other.pk, "function": "co_trainer"})
    client.post(reverse("occurrence_staff", args=[occurrence.pk]), {"user": trainer.pk, "function": "trainer"})
    functions = dict(occurrence.staffings.values_list("user__email", "function"))
    assert functions == {trainer.email: "trainer", other.email: "co_trainer"}


def test_confirm_from_my_staffings(client, trainer):
    occurrence = make_occurrence(in_days=-1)
    Staffing.objects.create(occurrence=occurrence, user=trainer, function=StaffFunction.TRAINER)
    login(client, trainer)
    assert "noch bestätigen" in client.get(reverse("my_staffings")).content.decode()
    client.post(reverse("staffing_confirm", args=[occurrence.pk]), {"minutes": "75"})
    assert Staffing.objects.get().minutes == 75


def test_event_management_only_for_head(client, head, trainer):
    login(client, trainer)
    assert client.get(reverse("event_list")).status_code == 200
    assert client.get(reverse("event_create")).status_code == 403
    assert client.get(reverse("target_group_list")).status_code == 403
    client.logout()
    login(client, head)
    response = client.post(reverse("event_create"), {"title": "Training U12", "kind": "training"})
    event = Event.objects.get()
    assert response.url == reverse("event_detail", args=[event.pk])
    today = timezone.localdate()
    client.post(
        reverse("schedule_create", args=[event.pk]),
        {
            "weekday": today.weekday(),
            "start_time": "17:00",
            "end_time": "18:30",
            "valid_from": (today + timedelta(days=1)).isoformat(),
            "valid_until": (today + timedelta(days=28)).isoformat(),
        },
    )
    assert event.occurrences.count() == 4
    assert client.get(reverse("event_detail", args=[event.pk])).status_code == 200


def test_target_group_pages(client, head, child):
    Interest.objects.create(name="Kata")
    login(client, head)
    client.post(reverse("target_group_create"), {"name": "U12", "max_age": "11", "genders": ["w"]})
    group = TargetGroup.objects.get()
    assert group.genders == ["w"]
    page = client.get(reverse("target_group_members", args=[group.pk])).content.decode()
    assert "Passen heute: 1" in page


def test_parent_without_trainer_role_sees_no_management(client, parent, child):
    login(client, parent)
    page = client.get(reverse("home")).content.decode()
    assert reverse("agenda") in page
    assert reverse("event_list") not in page
    assert client.get(reverse("event_list")).status_code == 403
    assert client.get(reverse("my_staffings")).status_code == 403


def test_phone_on_security_page(client, parent):
    login(client, parent)
    client.post(reverse("security"), {"phone": "0171 555"})
    parent.refresh_from_db()
    assert parent.phone == "0171 555"


def test_interest_self_service(client, parent, child):
    kata = Interest.objects.create(name="Kata")
    login(client, parent)
    client.post(reverse("my_member_edit", args=[child.pk]), {"interests": [kata.pk]})
    assert list(child.interests.all()) == [kata]
