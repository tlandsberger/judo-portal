from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

import pytest
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from portal.assistant import llm, services, tools
from portal.assistant.models import Conversation, Message, MessageRole
from portal.assistant.templatetags.uke import uke_text
from portal.events import services as events
from portal.events.models import Event
from portal.events.tests.conftest import (
    PASSWORD,
    make_member,
    make_occurrence,
    make_trainer,
    make_user,
    rates_not_required,  # noqa: F401 – Stundensätze hier egal
    role,
)
from portal.members.models import LinkKind, MemberLink
from portal.privacy import services as privacy


@pytest.fixture(autouse=True)
def _enabled(settings):
    settings.ASSISTANT_URL = "http://llm.test"


class Script:
    """Spielt das Modell: gibt nacheinander die vorbereiteten Antworten zurück und merkt sich, was es bekam."""

    def __init__(self, *replies: llm.Reply) -> None:
        self.replies = list(replies)
        self.calls: list[list[dict[str, Any]]] = []
        self.tools: list[list[str]] = []

    def __call__(self, messages: list[dict[str, Any]], specs: list[dict[str, Any]]) -> llm.Reply:
        self.calls.append([dict(m) for m in messages])
        self.tools.append([spec["function"]["name"] for spec in specs])
        return self.replies.pop(0)


def _ctx(user) -> tools.Context:
    request = RequestFactory().get("/uke/")
    request.user = user
    return tools.Context(request)


def _parent_with_child():
    parent = make_user("eltern@example.org")
    child = make_member("Max", age=10)
    MemberLink.objects.create(user=parent, member=child, kind=LinkKind.GUARDIAN)
    return parent, child


@pytest.mark.django_db
def test_page_only_when_configured(client, settings):
    user = make_user("eltern@example.org")
    client.force_login(user)
    assert client.get(reverse("assistant")).status_code == 200
    assert 'href="/uke/"' in client.get(reverse("home")).content.decode()
    settings.ASSISTANT_URL = ""
    assert client.get(reverse("assistant")).status_code == 404
    assert 'href="/uke/"' not in client.get(reverse("home")).content.decode()


@pytest.mark.django_db
def test_page_needs_login(client):
    assert client.get(reverse("assistant")).status_code == 302


@pytest.mark.django_db
def test_ask_runs_tool_and_keeps_links(monkeypatch):
    parent, child = _parent_with_child()
    occurrence = make_occurrence(Event.objects.create(title="Kindertraining"), in_days=1)
    events.register(occurrence, child, parent)
    script = Script(
        llm.Reply(tool_calls=[llm.ToolCall("c1", "termine_suchen", {"suche": "kinder"})]),
        llm.Reply("Max ist morgen beim Kindertraining angemeldet."),
    )
    monkeypatch.setattr(llm, "complete", script)
    conv = Conversation.objects.create(user=parent)

    question, answer = services.ask(_ctx(parent), conv, "Ist Max morgen angemeldet?")

    assert question.role == MessageRole.USER
    assert answer.content == "Max ist morgen beim Kindertraining angemeldet."
    assert answer.tools == ["termine_suchen"]
    assert answer.links == [tools._link(occurrence)]
    # Das Modell bekam das Ergebnis des Werkzeugs mit dem Status des eigenen Kindes
    result = json.loads(script.calls[1][-1]["content"])
    assert result["termine"][0]["eigene_mitglieder"] == [
        {"mitglied": str(child), "passt_zur_zielgruppe": "ja", "status": "Angemeldet"}
    ]
    assert "Max" in script.calls[0][0]["content"]  # eigene Mitglieder stehen im Systemprompt
    assert script.tools[0] == ["termine_suchen", "termin_details", "hilfe_suchen"]


@pytest.mark.django_db
def test_participants_only_with_right():
    parent, child = _parent_with_child()
    trainer = make_trainer()
    occurrence = make_occurrence(in_days=1)
    events.register(occurrence, child, parent)
    events.set_team(occurrence, trainer.member_links.get().member, role("Trainer"))

    for_parent = tools.occurrence_details(_ctx(parent), {"termin_id": occurrence.pk}).data
    for_trainer = tools.occurrence_details(_ctx(trainer), {"termin_id": occurrence.pk}).data

    assert "teilnehmer" not in for_parent
    assert for_trainer["teilnehmer"] == [{"name": str(child), "status": "Angemeldet"}]
    assert for_parent["uebungsleiter"] == ["Anna Trainer (Trainer)"]


@pytest.mark.django_db
def test_tool_errors_go_back_to_model(monkeypatch):
    user = make_user("eltern@example.org")
    script = Script(
        llm.Reply(
            tool_calls=[
                llm.ToolCall("c1", "termin_loeschen", {}),
                llm.ToolCall("c2", "termin_details", {"termin_id": "x"}),
                llm.ToolCall("c3", "termine_suchen", {"von": "morgen"}),
            ]
        ),
        llm.Reply("Das weiß ich nicht."),
    )
    monkeypatch.setattr(llm, "complete", script)

    services.ask(_ctx(user), Conversation.objects.create(user=user), "Lösch alles")

    errors = [json.loads(m["content"])["fehler"] for m in script.calls[1] if m["role"] == "tool"]
    assert errors == [
        "Das Werkzeug termin_loeschen gibt es nicht.",
        "termin_id fehlt; erst mit termine_suchen die ID herausfinden.",
        "von muss ein Datum im Format JJJJ-MM-TT sein.",
    ]


@pytest.mark.django_db
def test_search_starts_today_and_respects_range():
    user = make_user("eltern@example.org")
    soon = make_occurrence(in_days=2)
    make_occurrence(in_days=20)
    yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()

    data = tools.search_occurrences(_ctx(user), {"von": yesterday}).data

    assert [row["termin_id"] for row in data["termine"]] == [soon.pk]
    assert "hinweis_zeitraum" in data


@pytest.mark.django_db
def test_rounds_are_limited(monkeypatch):
    user = make_user("eltern@example.org")
    loop = [llm.Reply(tool_calls=[llm.ToolCall("c", "termine_suchen", {})]) for _ in range(services.MAX_ROUNDS)]
    monkeypatch.setattr(llm, "complete", Script(*loop))

    _, answer = services.ask(_ctx(user), Conversation.objects.create(user=user), "Termine?")

    assert answer.content == services.GAVE_UP


@pytest.mark.django_db
def test_unavailable_model(monkeypatch):
    user = make_user("eltern@example.org")

    def down(*args: Any) -> llm.Reply:
        raise llm.Unavailable("weg")

    monkeypatch.setattr(llm, "complete", down)
    conv = Conversation.objects.create(user=user)
    _, answer = services.ask(_ctx(user), conv, "Hallo")
    assert answer.failed and answer.content == services.UNAVAILABLE
    # Fehlgeschlagene Antworten gehen nicht in den Verlauf für das Modell
    assert services._history(conv) == [{"role": "user", "content": "Hallo"}]


@pytest.mark.django_db
def test_input_checks(monkeypatch):
    user = make_user("eltern@example.org")
    with pytest.raises(services.AssistantError):
        services.check(user, "   ")
    with pytest.raises(services.AssistantError):
        services.check(user, "x" * (services.MAX_INPUT + 1))
    conv = Conversation.objects.create(user=user)
    Message.objects.bulk_create(
        [Message(conversation=conv, role=MessageRole.USER, content="?") for _ in range(services.HOURLY_LIMIT)]
    )
    with pytest.raises(services.AssistantError, match="sehr viele"):
        services.check(user, "Noch eine")


@pytest.mark.django_db
def test_foreign_conversation_is_not_used(client):
    other = make_user("andere@example.org")
    foreign = Conversation.objects.create(user=other)
    Message.objects.create(conversation=foreign, role=MessageRole.USER, content="Geheime Frage")
    user = make_user("eltern@example.org")
    client.force_login(user)
    session = client.session
    session["assistant_conversation"] = foreign.pk
    session.save()

    assert "Geheime Frage" not in client.get(reverse("assistant")).content.decode()
    assert services.conversation(user, foreign.pk) is None


@pytest.mark.django_db
def test_chat_with_fake_model(client, settings):
    settings.ASSISTANT_URL = llm.FAKE
    user = make_user("eltern@example.org")
    make_occurrence(Event.objects.create(title="Kindertraining"), in_days=1)
    client.login(email=user.email, password=PASSWORD)

    partial = client.post(reverse("assistant_send"), {"frage": "Was steht an Terminen an?"}, HTTP_X_UKE="1")
    assert partial.status_code == 200
    assert "Ich habe 1 Termine gefunden" in partial.content.decode()
    assert "Kindertraining" in partial.content.decode()

    page = client.get(reverse("assistant")).content.decode()
    assert "Was steht an Terminen an?" in page and "Neues Gespräch" in page

    client.post(reverse("assistant_new"))
    assert "Was steht an Terminen an?" not in client.get(reverse("assistant")).content.decode()
    assert Message.objects.filter(conversation__user=user).count() == 2  # gespeichert bleibt es trotzdem

    error = client.post(reverse("assistant_send"), {"frage": ""}, HTTP_X_UKE="1")
    assert error.status_code == 400 and "Schreib bitte eine Frage" in error.content.decode()


@pytest.mark.django_db
def test_help_search():
    user = make_user("eltern@example.org")
    result = tools.search_help(_ctx(user), {"frage": "Wie richte ich einen Passkey ein?"})
    assert result.data and all("kapitel" in row for row in result.data)
    assert any("Passkey" in row["text"] for row in result.data)
    assert result.links


@pytest.mark.django_db
def test_cleanup_after_30_days():
    user = make_user("eltern@example.org")
    old = Conversation.objects.create(user=user)
    message = Message.objects.create(conversation=old, role=MessageRole.USER, content="alt")
    Message.objects.filter(pk=message.pk).update(created_at=timezone.now() - timedelta(days=31))
    Conversation.objects.filter(pk=old.pk).update(started_at=timezone.now() - timedelta(days=31))
    recent = Conversation.objects.create(user=user)
    Message.objects.create(conversation=recent, role=MessageRole.USER, content="neu")

    services.cleanup()

    assert list(Message.objects.values_list("content", flat=True)) == ["neu"]
    assert list(Conversation.objects.all()) == [recent]


@pytest.mark.django_db
def test_privacy_export_and_deletion():
    user = make_user("eltern@example.org")
    conv = Conversation.objects.create(user=user)
    Message.objects.create(conversation=conv, role=MessageRole.USER, content="Wann ist Training?")
    Message.objects.create(conversation=conv, role=MessageRole.ASSISTANT, content="Mittwoch.")

    data = privacy.export(user)
    texts = [(m["Von"], m["Text"]) for m in data["Gespräche mit Uke"][0]["Nachrichten"]]
    assert texts == [("Du", "Wann ist Training?"), ("Uke", "Mittwoch.")]
    privacy.delete_user(user, None, privacy.REASON_REQUEST, notify=False)
    assert not Message.objects.exists()


def test_parse_strips_thinking_and_reads_arguments():
    reply = llm.parse(
        {
            "choices": [
                {
                    "message": {
                        "content": "<think>hm</think>\nOk",
                        "tool_calls": [
                            {"id": "a", "function": {"name": "termin_details", "arguments": '{"termin_id": 4}'}}
                        ],
                    }
                }
            ]
        }
    )
    assert reply.content == "Ok"
    assert reply.tool_calls == [llm.ToolCall("a", "termin_details", {"termin_id": 4})]
    with pytest.raises(llm.Unavailable):
        llm.parse({"error": "x"})


def test_answer_text_is_escaped():
    html = uke_text("Hallo <script>x</script>\n- **Mi** 18 Uhr\n- Fr")
    assert "<script>" not in html
    assert html == (
        "<p>Hallo &lt;script&gt;x&lt;/script&gt;</p>"
        '<ul class="list-disc ps-5"><li><strong>Mi</strong> 18 Uhr</li><li>Fr</li></ul>'
    )


def test_links_from_model_are_removed():
    assert services.clean("Siehe 👉 [Zum Termin](https://example.org/t/1) oder https://evil.example/x.") == (
        "Siehe 👉 Zum Termin oder."
    )


@pytest.mark.django_db
def test_search_with_count_lists_participants_for_team_only():
    parent, child = _parent_with_child()
    trainer = make_trainer()
    first = make_occurrence(in_days=1)
    make_occurrence(in_days=2)
    events.register(first, child, parent)
    events.set_team(first, trainer.member_links.get().member, role("Trainer"))

    for_trainer = tools.search_occurrences(_ctx(trainer), {"anzahl": 1}).data
    for_parent = tools.search_occurrences(_ctx(parent), {"anzahl": 1}).data

    assert for_trainer["anzahl"] == 2 and len(for_trainer["termine"]) == 1
    assert for_trainer["termine"][0]["teilnehmer"] == [f"{child} (Angemeldet)"]
    assert "teilnehmer" not in for_parent["termine"][0] and "angemeldet" not in for_parent["termine"][0]
