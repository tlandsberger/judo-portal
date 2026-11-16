"""Push-Benachrichtigungen mit Mail als Ersatz, einmal je Schlüssel, Aktionen mit signiertem Token."""

from __future__ import annotations

import json
from datetime import timedelta
from types import SimpleNamespace

import pytest
import pywebpush
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from portal.accounts.models import User
from portal.notifications import services
from portal.notifications.models import Channel, PushNotificationSubscription, SentNotification
from portal.notifications.services import Action, ActionResult

pytestmark = pytest.mark.django_db


@pytest.fixture
def vapid(settings):
    settings.VAPID_PUBLIC_KEY = "public"
    settings.VAPID_PRIVATE_KEY = "private"


@pytest.fixture
def push_notifications(monkeypatch):
    """Ersetzt webpush; ``failing`` legt fest, welche Endpoints mit welchem Status scheitern."""
    sent: list[dict] = []
    failing: dict[str, int] = {}

    def fake(subscription_info, data, **kwargs):
        endpoint = subscription_info["endpoint"]
        if endpoint in failing:
            raise pywebpush.WebPushException("kaputt", response=SimpleNamespace(status_code=failing[endpoint]))
        sent.append({"endpoint": endpoint, "urgency": kwargs.get("headers", {}).get("Urgency"), **json.loads(data)})

    monkeypatch.setattr(pywebpush, "webpush", fake)
    return SimpleNamespace(sent=sent, failing=failing)


@pytest.fixture
def user() -> User:
    return User.objects.create_user("eltern@example.org", first_name="Eva")


def device(user: User, name: str = "a") -> PushNotificationSubscription:
    return services.subscribe(user, f"https://push.example/{name}", "key", "auth", "Chrome auf Android")


def send(user: User, key: str = "k1", **extra) -> bool:
    return services.notify(
        user, key=key, kind="test", title="Abgesagt: Training", body="Fällt aus.", url="/termine/1/", **extra
    )


def test_push_notification_instead_of_mail(vapid, push_notifications, user, django_capture_on_commit_callbacks):
    device(user)
    with django_capture_on_commit_callbacks(execute=True):
        assert send(user, actions=[Action("register", "Anmelden", {"o": 1})])
    assert mail.outbox == []
    [push] = push_notifications.sent
    assert push["title"] == "Abgesagt: Training" and push["url"] == "/termine/1/"
    assert push["actions"][0]["title"] == "Anmelden" and push["actions"][0]["token"]
    assert SentNotification.objects.get().channel == Channel.PUSH_NOTIFICATION


def test_mail_without_device(vapid, push_notifications, user, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        send(user)
    assert push_notifications.sent == []
    assert mail.outbox[0].subject.endswith("Abgesagt: Training")
    assert "Fällt aus." in mail.outbox[0].body
    assert SentNotification.objects.get().channel == Channel.MAIL


def test_mail_without_vapid_keys(push_notifications, user, django_capture_on_commit_callbacks):
    device(user)
    with django_capture_on_commit_callbacks(execute=True):
        send(user)
    assert push_notifications.sent == [] and len(mail.outbox) == 1


def test_gone_subscription_removed_and_mail_sent(vapid, push_notifications, user, django_capture_on_commit_callbacks):
    device(user, "alt")
    push_notifications.failing["https://push.example/alt"] = 410
    with django_capture_on_commit_callbacks(execute=True):
        send(user)
    assert not PushNotificationSubscription.objects.exists()
    assert len(mail.outbox) == 1


def test_one_device_enough(vapid, push_notifications, user, django_capture_on_commit_callbacks):
    device(user, "alt")
    device(user, "neu")
    push_notifications.failing["https://push.example/alt"] = 500
    with django_capture_on_commit_callbacks(execute=True):
        send(user)
    assert len(push_notifications.sent) == 1 and mail.outbox == []
    assert PushNotificationSubscription.objects.count() == 2  # 500 ist vorübergehend, das Abo bleibt


def test_only_once_per_key(vapid, push_notifications, user, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        assert send(user)
        assert not send(user)
    assert len(mail.outbox) == 1


def test_cleanup_removes_old_records(user):
    SentNotification.objects.create(
        key="alt", user=user, kind="x", title="x", created_at=timezone.now() - timedelta(days=91)
    )
    SentNotification.objects.create(key="neu", user=user, kind="x", title="x")
    services.cleanup()
    assert list(SentNotification.objects.values_list("key", flat=True)) == ["neu"]


def test_action_token(user, client, monkeypatch):
    calls = []

    def handler(acting_user, data):
        calls.append((acting_user, data))
        return ActionResult(True, "Mia ist angemeldet.")

    services.register_action("probe", handler)
    token = Action("probe", "Probe", {"o": 7}).token(user)
    response = client.post(reverse("push_notification_action"), {"token": token})
    assert response.json() == {"ok": True, "message": "Mia ist angemeldet.", "url": "/"}
    assert calls == [(user, {"o": 7})]
    # manipuliert, unbekannt, abgelaufen, gesperrter Benutzer
    assert not client.post(reverse("push_notification_action"), {"token": token + "x"}).json()["ok"]
    assert not services.run_action(Action("gibt-es-nicht", "x").token(user)).ok
    with monkeypatch.context() as patch:
        patch.setattr(services, "ACTION_MAX_AGE", timedelta(seconds=-1))
        assert "abgelaufen" in services.run_action(token).message
    user.is_active = False
    user.save()
    assert not services.run_action(token).ok
    assert len(calls) == 1


def test_subscribe_views(vapid, client, user):
    client.force_login(user)
    payload = {"endpoint": "https://push.example/x", "keys": {"p256dh": "k", "auth": "a"}}
    response = client.post(
        reverse("push_notification_subscribe"),
        json.dumps(payload),
        content_type="application/json",
        HTTP_USER_AGENT="Mozilla/5.0 (Linux; Android 14) Chrome/130.0 Mobile Safari/537.36",
    )
    assert response.status_code == 200
    subscription = PushNotificationSubscription.objects.get()
    assert subscription.user == user and subscription.device == "Chrome auf Android"
    bad = client.post(
        reverse("push_notification_subscribe"), json.dumps({"endpoint": "http://x"}), content_type="application/json"
    )
    assert bad.status_code == 400
    page = client.get(reverse("security")).content.decode()
    assert "Chrome auf Android" in page and "Push-Benachrichtigungen auf diesem Gerät einschalten" in page
    other = User.objects.create_user("andere@example.org")
    foreign = device(other, "fremd")
    assert client.post(reverse("push_notification_remove_device", args=[foreign.pk])).status_code == 404
    client.post(
        reverse("push_notification_unsubscribe"),
        json.dumps({"endpoint": "https://push.example/x"}),
        content_type="application/json",
    )
    assert not PushNotificationSubscription.objects.filter(user=user).exists()


def test_without_keys_no_push_notifications_offered(client, user):
    client.force_login(user)
    page = client.get(reverse("security")).content.decode()
    assert "Benachrichtigungen bekommst du per E-Mail." in page
    assert client.post(reverse("push_notification_subscribe"), "{}", content_type="application/json").status_code == 400


def test_urgency_high_only_for_time_critical(vapid, push_notifications, user, django_capture_on_commit_callbacks):
    device(user)
    with django_capture_on_commit_callbacks(execute=True):
        services.notify(user, key="a", kind="cancelled", title="Abgesagt", body="", url="/")
        services.notify(user, key="b", kind="registration_open", title="Anmeldung offen", body="", url="/")
    assert [push["urgency"] for push in push_notifications.sent] == ["high", "normal"]


def test_android_hint_only_on_android(vapid, client, user):
    client.force_login(user)
    android = "Mozilla/5.0 (Linux; Android 15; Pixel 9) Chrome/140.0 Mobile Safari/537.36"
    assert "Nicht eingeschränkt" in client.get("/zugang/anmeldung/", HTTP_USER_AGENT=android).content.decode()
    assert "Nicht eingeschränkt" not in client.get("/zugang/anmeldung/").content.decode()
