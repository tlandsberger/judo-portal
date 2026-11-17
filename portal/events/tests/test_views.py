from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from portal.events import services
from portal.events.models import (
    Event,
    ParticipantRole,
    Participation,
    ParticipationStatus,
    TargetGroup,
    TargetGroupTemplate,
)
from portal.members.models import Interest

from .conftest import PASSWORD, event_type, make_member, make_occurrence, make_trainer, role

pytestmark = pytest.mark.django_db


def login(client, user):
    assert client.login(email=user.email, password=PASSWORD)
    return client


def groups(*blocks: dict, initial: int = 0) -> dict:
    """Formset-Daten für die Zielgruppen im Formular der Veranstaltung."""
    data = {"zg-TOTAL_FORMS": str(len(blocks)), "zg-INITIAL_FORMS": str(initial)}
    for index, block in enumerate(blocks):
        data.update({f"zg-{index}-{name}": value for name, value in block.items()})
    return data


def test_agenda_quick_registration(client, parent, child):
    occurrence = make_occurrence()
    login(client, parent)
    page = client.get(reverse("agenda"))
    assert page.status_code == 200
    assert "Training" in page.content.decode()
    client.post(reverse("register", args=[occurrence.pk, child.pk]), {"next": reverse("agenda")})
    assert Participation.objects.get().status == ParticipationStatus.REGISTERED
    client.post(reverse("unregister", args=[occurrence.pk, child.pk]))
    assert Participation.objects.get().status == ParticipationStatus.CANCELLED


def test_register_form_with_weight(client, parent, child):
    occurrence = make_occurrence(
        Event.objects.create(title="Wettkampf", event_type=event_type("Wettkampf"), weight_required=True)
    )
    login(client, parent)
    page = client.get(reverse("register", args=[occurrence.pk, child.pk]))
    assert "Gewicht" in page.content.decode()
    client.post(reverse("register", args=[occurrence.pk, child.pk]))  # ohne Formular: nicht angemeldet
    assert not Participation.objects.exists()
    client.post(reverse("register", args=[occurrence.pk, child.pk]), {"form": "1", "weight": "31,5", "note": ""})
    child.refresh_from_db()
    assert str(child.weight) == "31.5"
    assert Participation.objects.get().weight == child.weight


def test_cannot_register_foreign_member(client, parent):
    stranger = make_member("Ole")
    occurrence = make_occurrence()
    login(client, parent)
    assert client.post(reverse("register", args=[occurrence.pk, stranger.pk])).status_code == 403


def test_participants_only_for_own_team(client, trainer, parent, child):
    other = make_trainer("tom@example.org", "Tom")
    occurrence = make_occurrence()
    services.set_team(occurrence, services.own_member(trainer), role("Trainer"))
    services.register(occurrence, child, parent)
    page = login(client, trainer).get(reverse("occurrence_detail", args=[occurrence.pk])).content.decode()
    assert "Teilnehmer (1)" in page and parent.email in page
    client.logout()
    page = login(client, other).get(reverse("occurrence_detail", args=[occurrence.pk])).content.decode()
    assert "Teilnehmer" not in page and parent.email not in page
    assert client.get(reverse("participant_add", args=[occurrence.pk])).status_code == 403
    assert client.get(reverse("member_list")).status_code == 403


def test_trainer_adds_self_and_exception(client, trainer, child):
    occurrence = make_occurrence(Event.objects.create(title="Kader"))
    TargetGroup.objects.create(event=occurrence.event, name="Erwachsene", min_age=18)
    login(client, trainer)
    page = client.get(reverse("occurrence_detail", args=[occurrence.pk])).content.decode()
    assert "Mich als Trainer eintragen" in page and "Mich als Prüfer" not in page
    client.post(reverse("occurrence_team", args=[occurrence.pk]), {"role": role("Trainer").pk})
    assert occurrence.participations.get().role.name == "Trainer"
    results = client.get(reverse("participant_add", args=[occurrence.pk]), {"q": "Mi"}).content.decode()
    assert child.display_name in results
    client.post(reverse("participant_add", args=[occurrence.pk]), {"member": child.pk})
    assert Participation.objects.get(member=child).exception_by == trainer


def test_trainer_changes_role_of_others(client, trainer):
    other = make_trainer("tom@example.org", "Tom")
    occurrence = make_occurrence()
    anna, tom = services.own_member(trainer), services.own_member(other)
    services.set_team(occurrence, anna, role("Co-Trainer"))
    services.set_team(occurrence, tom, role("Trainer"))
    login(client, trainer)
    url = reverse("occurrence_team", args=[occurrence.pk])
    client.post(url, {"member": tom.pk, "role": role("Co-Trainer").pk})
    client.post(url, {"member": anna.pk, "role": role("Trainer").pk})
    roles = dict(occurrence.participations.values_list("member__first_name", "role__name"))
    assert roles == {"Anna": "Trainer", "Tom": "Co-Trainer"}


def test_confirm_from_billing_index(client, trainer):
    past = make_occurrence(in_days=-1)
    coming = make_occurrence(in_days=2)
    anna = services.own_member(trainer)
    services.set_team(past, anna, role("Trainer"))
    services.set_team(coming, anna, role("Trainer"))
    login(client, trainer)
    page = client.get(reverse("billing_index")).content.decode()
    assert "Noch bestätigen" in page
    assert reverse("occurrence_detail", args=[past.pk]) + "#h-team" in page  # „Nicht dabei?“
    assert reverse("occurrence_detail", args=[coming.pk]) + "#h-team" not in page
    response = client.post(
        reverse("hours_confirm", args=[past.pk]), {"minutes": "75", "next": reverse("billing_index")}
    )
    assert response.url == reverse("billing_index")
    assert Participation.objects.get(occurrence=past).minutes == 75
    assert "Noch bestätigen" not in client.get(reverse("billing_index")).content.decode()


def test_event_management_only_for_head(client, head, trainer):
    login(client, trainer)
    assert client.get(reverse("event_list")).status_code == 200
    assert client.get(reverse("event_create")).status_code == 403
    assert client.get(reverse("target_group_list")).status_code == 403
    client.logout()
    login(client, head)
    response = client.post(
        reverse("event_create"),
        {"title": "Training U12", "event_type": event_type("Training").pk, "dates": "later", **groups()},
    )
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
    group = TargetGroupTemplate.objects.get()
    assert group.genders == ["w"]
    page = client.get(reverse("target_group_members", args=[group.pk])).content.decode()
    assert "Passen heute: 1" in page


def test_parent_without_trainer_role_sees_no_management(client, parent, child):
    login(client, parent)
    page = client.get(reverse("home")).content.decode()
    assert reverse("agenda") in page
    assert reverse("event_list") not in page
    assert client.get(reverse("event_list")).status_code == 403
    assert client.get(reverse("billing_index")).status_code == 403


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


def test_role_and_event_type_pages(client, head, trainer):
    login(client, head)
    page = client.get(reverse("role_list")).content.decode()
    assert "Co-Trainer" in page and "abrechnungsrelevant" in page
    client.post(
        reverse("role_create"),
        {"name": "Kampfrichter", "order": 50, "user_roles": ["trainer"], "is_team": "on", "is_active": "on"},
    )
    assert ParticipantRole.objects.get(name="Kampfrichter").is_team
    # „Rolle bei Anmeldung“ umsetzen
    helper = ParticipantRole.objects.get(name="Kampfrichter")
    client.post(
        reverse("role_edit", args=[helper.pk]),
        {"name": "Kampfrichter", "order": 50, "is_default": "on", "is_active": "on"},
    )
    assert services.default_role() == helper
    # benutzte Rolle lässt sich nicht löschen
    services.set_team(make_occurrence(), services.own_member(trainer), role("Trainer"))
    client.post(reverse("role_delete", args=[role("Trainer").pk]))
    assert ParticipantRole.objects.filter(name="Trainer").exists()
    client.post(reverse("event_type_create"), {"name": "Ausflug", "order": 60, "is_active": "on"})
    assert "Ausflug" in client.get(reverse("event_type_list")).content.decode()


def test_create_event_weekly_with_team(client, head, trainer):
    login(client, head)
    today = timezone.localdate()
    anna = services.own_member(trainer)
    client.post(
        reverse("event_create"),
        {
            "title": "Training U12",
            "event_type": event_type("Training").pk,
            "dates": "weekly",
            "weekdays": ["1", "3"],
            "start_time": "17:00",
            "end_time": "18:30",
            "valid_from": today.isoformat(),
            "valid_until": (today + timedelta(days=27)).isoformat(),
            "opens_hours_before": "72",
            "closes_hours_before": "2",
            "team_member": anna.pk,
            "team_role": role("Trainer").pk,
            **groups(),
        },
    )
    event = Event.objects.get()
    assert [s.weekday for s in event.schedules.all()] == [1, 3]
    assert event.occurrences.count() == 8
    first = event.occurrences.first()
    assert first.registration_closes == first.starts_at - timedelta(hours=2)
    assert all(o.participations.get().role.name == "Trainer" for o in event.occurrences.all())


def test_create_event_once_and_validation(client, head, trainer):
    login(client, head)
    base = {"title": "Turnier", "event_type": event_type("Wettkampf").pk, "dates": "once", **groups()}
    page = client.post(reverse("event_create"), base)
    assert "Bitte ausfüllen." in page.content.decode()
    # Trainer gibt es bei Wettkämpfen nicht: nichts wird angelegt
    starts = timezone.localtime() + timedelta(days=20)
    once = {
        **base,
        "starts_at": starts.strftime("%Y-%m-%dT10:00"),
        "ends_at": starts.strftime("%Y-%m-%dT16:00"),
        "registration_closes_at": (starts - timedelta(days=7)).strftime("%Y-%m-%dT20:00"),
        "team_member": services.own_member(trainer).pk,
    }
    page = client.post(reverse("event_create"), {**once, "team_role": role("Trainer").pk})
    assert "nicht Trainer sein" in page.content.decode()
    assert not Event.objects.exists()
    client.post(reverse("event_create"), {**once, "team_role": role("Betreuer").pk})
    occurrence = Event.objects.get().occurrences.get()
    assert occurrence.registration_closes_at is not None
    assert occurrence.participations.get().role.name == "Betreuer"


def test_open_and_delete_from_the_entry(client, head):
    """Titel öffnet Zeitplan bzw. Interesse; gelöscht wird erst dort, nicht in der Liste (ADR 0017)."""
    from .test_schedules import schedule

    event = Event.objects.create(title="Training U12")
    plan = schedule(event, weekday=0)
    interest = Interest.objects.create(name="Kata")
    login(client, head)
    detail = client.get(reverse("event_detail", args=[event.pk])).content.decode()
    assert f'href="{reverse("schedule_edit", args=[event.pk, plan.pk])}"' in detail
    assert reverse("schedule_delete", args=[event.pk, plan.pk]) not in detail
    assert (
        reverse("schedule_delete", args=[event.pk, plan.pk])
        in client.get(reverse("schedule_edit", args=[event.pk, plan.pk])).content.decode()
    )
    listing = client.get(reverse("interest_list")).content.decode()
    assert f'href="{reverse("interest_edit", args=[interest.pk])}"' in listing
    assert reverse("interest_delete", args=[interest.pk]) not in listing
    assert (
        reverse("interest_delete", args=[interest.pk])
        in client.get(reverse("interest_edit", args=[interest.pk])).content.decode()
    )
