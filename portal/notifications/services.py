"""Benachrichtigungen für den täglichen Ablauf: Push auf alle Geräte des Benutzers, sonst per Mail (ADR 0011).

Kritisches (Einladung, Anmeldecode, Sicherheit des Zugangs, neue Verknüpfung) geht nicht hierüber, sondern immer
direkt per Mail.

Aktionsknöpfe an Push-Nachrichten tragen einen signierten Link. Was eine Aktion tut, melden die Fach-Apps über
``register_action`` an; dieses Modul kennt sie nicht.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from portal.accounts.models import User

from .models import Channel, PushSubscription, SentNotification

log = logging.getLogger(__name__)

ACTION_SALT = "portal.notifications.action"
ACTION_MAX_AGE = timedelta(days=7)
KEEP_DAYS = 90
PUSH_TTL = 24 * 60 * 60
# Zeitkritisches weckt Android sofort (Urgency „high“); der Rest kommt im nächsten Wartungsfenster des Ruhemodus.
# Bewusst sparsam: Android drosselt Absender, deren dringende Nachrichten oft nicht angesehen werden.
URGENT_KINDS = frozenset({"cancelled", "changed", "promoted", "deadline"})


def push_enabled() -> bool:
    return bool(settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY)


def has_push(user: User) -> bool:
    return push_enabled() and user.push_subscriptions.exists()


# Aktionen


@dataclass
class ActionResult:
    """Ergebnis einer Aktion: kurze Rückmeldung als Nachricht; bei ``ok=False`` öffnet sich ``url``."""

    ok: bool
    message: str
    url: str = "/"


ActionHandler = Callable[[User, dict[str, Any]], ActionResult]
_actions: dict[str, ActionHandler] = {}


def register_action(name: str, handler: ActionHandler) -> None:
    _actions[name] = handler


@dataclass
class Action:
    """Knopf an einer Push-Nachricht, z. B. „Anmelden“."""

    name: str
    title: str
    data: dict[str, Any] = field(default_factory=dict)

    def token(self, user: User) -> str:
        return signing.dumps({"u": user.pk, "a": self.name, "d": self.data}, salt=ACTION_SALT, compress=True)


def run_action(token: str) -> ActionResult:
    """Führt eine Aktion aus einem Push-Knopf aus. Der Token ersetzt Anmeldung und CSRF-Schutz."""
    try:
        data = signing.loads(token, salt=ACTION_SALT, max_age=ACTION_MAX_AGE)
    except signing.SignatureExpired:
        return ActionResult(False, "Der Knopf ist abgelaufen. Öffne bitte das Portal.")
    except signing.BadSignature:
        return ActionResult(False, "Das hat nicht geklappt. Öffne bitte das Portal.")
    user = User.objects.filter(pk=data.get("u"), is_active=True).first()
    handler = _actions.get(data.get("a", ""))
    if user is None or handler is None:
        return ActionResult(False, "Das hat nicht geklappt. Öffne bitte das Portal.")
    return handler(user, data.get("d") or {})


# Versand


def notify(
    user: User,
    *,
    key: str,
    kind: str,
    title: str,
    body: str,
    url: str,
    actions: Iterable[Action] = (),
) -> bool:
    """Benachrichtigt einen Benutzer einmal je ``key``: per Push, wenn ein Gerät es annimmt, sonst per Mail.

    Gibt ``False`` zurück, wenn der Schlüssel schon vergeben war. Verschickt wird nach dem Commit.
    """
    if not user.is_active:
        return False
    try:
        with transaction.atomic():
            record = SentNotification.objects.create(key=key[:200], user=user, kind=kind, title=title[:120])
    except IntegrityError:
        return False
    action_list = list(actions)
    transaction.on_commit(lambda: _deliver(record, body, url, action_list))
    return True


def _deliver(record: SentNotification, body: str, url: str, actions: list[Action]) -> None:
    user = record.user
    payload = {
        "title": record.title,
        "body": body,
        "url": url,
        "tag": record.key,
        "actions": [{"action": a.name, "title": a.title, "token": a.token(user)} for a in actions],
    }
    urgency = "high" if record.kind in URGENT_KINDS else "normal"
    channel = Channel.PUSH if push_to_user(user, payload, urgency) else Channel.MAIL
    if channel == Channel.MAIL:
        send_mail(user, record.title, body, url)
    SentNotification.objects.filter(pk=record.pk).update(channel=channel)


def push_to_user(user: User, payload: dict[str, Any], urgency: str = "normal") -> bool:
    """Push an alle Geräte. Wahr, wenn mindestens eines die Nachricht angenommen hat."""
    if not push_enabled():
        return False
    delivered = False
    for subscription in PushSubscription.objects.filter(user=user):
        if send_push(subscription, payload, urgency):
            delivered = True
    return delivered


def send_push(subscription: PushSubscription, payload: dict[str, Any], urgency: str = "normal") -> bool:
    from pywebpush import WebPushException, webpush

    try:
        webpush(
            subscription_info=subscription.as_subscription_info(),
            data=json.dumps(payload),
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": settings.VAPID_SUBJECT},
            ttl=PUSH_TTL,
            headers={"Urgency": urgency},
            timeout=10,
        )
    except WebPushException as error:
        status = getattr(error.response, "status_code", None)
        if status in (404, 410):
            log.info("Push-Abo %s ist abgelaufen und wird entfernt", subscription.pk)
            subscription.delete()
        else:
            log.warning("Push an Abo %s fehlgeschlagen: %s", subscription.pk, status or error)
        return False
    except Exception:
        log.exception("Push an Abo %s fehlgeschlagen", subscription.pk)
        return False
    PushSubscription.objects.filter(pk=subscription.pk).update(last_used_at=timezone.now())
    return True


def send_mail(user: User, title: str, body: str, url: str) -> None:
    context = {"user": user, "title": title, "body": body, "url": _absolute(url), "base_url": settings.BASE_URL}
    message = EmailMultiAlternatives(
        subject=settings.EMAIL_SUBJECT_PREFIX + title,
        body=render_to_string("notifications/email/notification.txt", context),
        to=[user.email],
    )
    message.attach_alternative(render_to_string("notifications/email/notification.html", context), "text/html")
    message.send()


def _absolute(url: str) -> str:
    return url if url.startswith("http") else settings.BASE_URL + url


# Geräte


def subscribe(user: User, endpoint: str, p256dh: str, auth: str, device: str) -> PushSubscription:
    subscription, _ = PushSubscription.objects.update_or_create(
        endpoint=endpoint, defaults={"user": user, "p256dh": p256dh, "auth": auth, "device": device[:100]}
    )
    return subscription


def unsubscribe(user: User, endpoint: str) -> None:
    PushSubscription.objects.filter(user=user, endpoint=endpoint).delete()


def send_test(subscription: PushSubscription) -> bool:
    return send_push(
        subscription,
        {
            "title": "Push funktioniert",
            "body": "So sehen Benachrichtigungen von Wedeler TSV Judo aus.",
            "url": reverse("security"),
            "tag": "test",
            "actions": [],
        },
        "high",
    )


def cleanup() -> None:
    """Nächtlich: altes Versandprotokoll löschen."""
    SentNotification.objects.filter(created_at__lt=timezone.now() - timedelta(days=KEEP_DAYS)).delete()
