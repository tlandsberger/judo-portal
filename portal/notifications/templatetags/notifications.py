from __future__ import annotations

from typing import Any

from django import template
from django.conf import settings

from .. import services

register = template.Library()


@register.simple_tag(takes_context=True)
def push_notification_settings(context: dict[str, Any], user: Any) -> dict[str, Any]:
    """Für „Meine Anmeldung“ und die Startseite: Push-Benachrichtigungen eingerichtet, Geräte des Benutzers."""
    request = context.get("request")
    user_agent = request.headers.get("User-Agent", "") if request is not None else ""
    enabled = services.push_notifications_enabled()
    devices = list(user.push_notification_subscriptions.all()) if enabled and user.is_authenticated else []
    return {
        "enabled": enabled,
        "public_key": settings.VAPID_PUBLIC_KEY,
        "devices": devices,
        "endpoints": [device.endpoint for device in devices],
        "android": "Android" in user_agent,
    }
