from __future__ import annotations

from typing import Any

from django import template
from django.conf import settings

from .. import services

register = template.Library()


@register.simple_tag
def push_settings(user: Any) -> dict[str, Any]:
    """Für „Meine Anmeldung“ und die Startseite: ist Push eingerichtet, welche Geräte hat der Benutzer."""
    enabled = services.push_enabled()
    devices = list(user.push_subscriptions.all()) if enabled and user.is_authenticated else []
    return {
        "enabled": enabled,
        "public_key": settings.VAPID_PUBLIC_KEY,
        "devices": devices,
        "endpoints": [device.endpoint for device in devices],
    }
