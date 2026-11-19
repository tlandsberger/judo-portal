"""Zielgruppen an der Veranstaltung und Vorlagen (ADR 0010)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.urls import reverse

from portal.events import services
from portal.events.models import Event, TargetGroup, TargetGroupTemplate
from portal.members.models import Interest

from .conftest import event_type, make_member
from .test_views import groups, login

pytestmark = pytest.mark.django_db


def edit(client, event: Event, *blocks: dict, initial: int = 0):
    data = {"title": event.title, "event_type": event.event_type_id, **groups(*blocks, initial=initial)}
    return client.post(reverse("event_edit", args=[event.pk]), data)


def test_create_with_two_blocks_and_or(client, head):
    login(client, head)
    client.post(
        reverse("event_create"),
        {
            "title": "Randori",
            "event_type": event_type("Training").pk,
            "dates": "later",
            **groups({"name": "U11", "max_age": "10"}, {"min_age": "18", "genders": ["w"]}),
        },
    )
    event = Event.objects.get()
    assert [str(group) for group in event.target_groups.all()] == ["U11", "Alter ab 18 · weiblich"]
    assert not TargetGroupTemplate.objects.exists()
    assert services.match_event(event, make_member("Kim", age=9), services.timezone.localdate())
    assert not services.match_event(event, make_member("Tom", age=30, gender="m"), services.timezone.localdate())


def test_edit_adds_changes_and_removes_blocks(client, head):
    event = Event.objects.create(title="Training")
    group = TargetGroup.objects.create(event=event, name="U11", max_age=10)
    login(client, head)
    response = edit(
        client,
        event,
        {"id": group.pk, "event": event.pk, "name": "U13", "max_age": "12"},
        {"min_weight": "40,5"},
        initial=1,
    )
    assert response.status_code == 302
    assert [(g.name, g.max_age, g.min_weight) for g in event.target_groups.all()] == [
        ("U13", 12, None),
        ("", None, Decimal("40.5")),
    ]
    first, second = event.target_groups.all()
    edit(
        client,
        event,
        {"id": first.pk, "event": event.pk, "name": "U13", "max_age": "12", "DELETE": "on"},
        {"id": second.pk, "event": event.pk, "min_weight": "40,5"},
        initial=2,
    )
    assert list(event.target_groups.all()) == [second]


def test_block_validates_ranges(client, head):
    event = Event.objects.create(title="Training")
    login(client, head)
    page = edit(client, event, {"min_age": "12", "max_age": "10"}).content.decode()
    assert "Alter bis muss mindestens Alter ab sein." in page
    assert not event.target_groups.exists()


def test_save_as_template(client, head):
    kata = Interest.objects.create(name="Kata")
    event = Event.objects.create(title="Kata-Lehrgang")
    login(client, head)
    page = edit(client, event, {"max_age": "14", "save_as_template": "on"}).content.decode()
    assert "braucht die Zielgruppe eine Bezeichnung" in page
    edit(client, event, {"name": "Kata U15", "max_age": "14", "interests": [kata.pk], "save_as_template": "on"})
    template = TargetGroupTemplate.objects.get()
    assert (template.name, template.max_age, list(template.interests.all())) == ("Kata U15", 14, [kata])
    other = Event.objects.create(title="Zweiter Lehrgang")
    page = edit(client, other, {"name": "kata u15", "save_as_template": "on"}).content.decode()
    assert "gibt es schon" in page
    assert TargetGroupTemplate.objects.count() == 1


def test_template_is_copied_not_linked(head):
    kata = Interest.objects.create(name="Kata")
    template = TargetGroupTemplate.objects.create(name="U15", max_age=14)
    template.interests.set([kata])
    event = Event.objects.create(title="Training")
    group = template.apply_to(event)
    assert (group.name, group.max_age, list(group.interests.all())) == ("U15", 14, [kata])
    template.max_age = 16
    template.save()
    group.refresh_from_db()
    assert group.max_age == 14
    template.delete()
    assert event.target_groups.get() == group


def test_form_offers_templates(client, head):
    TargetGroupTemplate.objects.create(name="Erwachsene", min_age=18, min_weight=Decimal("60.5"))
    login(client, head)
    page = client.get(reverse("event_create")).content.decode()
    assert "Aus Vorlage übernehmen" in page
    assert '"min_weight": "60,5"' in page
    assert "data-target-group-remove" in page and "Zielgruppe entfernen</button>" in page  # Knopf statt Kästchen


def test_preview_only_for_managers(client, head, trainer, child):
    event = Event.objects.create(title="Kindertraining")
    TargetGroup.objects.create(event=event, max_age=12)
    make_member("Ole", age=40)
    login(client, head)
    page = client.get(reverse("event_detail", args=[event.pk])).content.decode()
    assert "Passende Mitglieder: 1" in page
    client.logout()
    login(client, trainer)
    page = client.get(reverse("event_detail", args=[event.pk])).content.decode()
    assert "Passende Mitglieder" not in page


@pytest.mark.django_db(transaction=True)
def test_migration_copies_groups_into_events():
    executor = MigrationExecutor(connection)
    executor.migrate([("events", "0003_guests")])
    apps = executor.loader.project_state([("events", "0003_guests")]).apps
    old_group = apps.get_model("events", "TargetGroup")
    old_event = apps.get_model("events", "Event")
    interest = apps.get_model("members", "Interest").objects.create(name="Kata")
    group = old_group.objects.create(name="U15", max_age=14, genders=["w"])
    group.interests.set([interest])
    kind = apps.get_model("events", "EventType").objects.get_or_create(name="Training")[0]
    first = old_event.objects.create(title="Training", event_type=kind)
    second = old_event.objects.create(title="Lehrgang", event_type=kind)
    first.target_groups.set([group])
    second.target_groups.set([group])

    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(executor.loader.graph.leaf_nodes())

    assert TargetGroupTemplate.objects.get().name == "U15"
    for pk in (first.pk, second.pk):
        copy = TargetGroup.objects.get(event_id=pk)
        assert (copy.name, copy.max_age, copy.genders) == ("U15", 14, ["w"])
        assert [i.name for i in copy.interests.all()] == ["Kata"]
