from __future__ import annotations

from typing import Any

from django.http import HttpRequest

from . import services


def events(request: HttpRequest) -> dict[str, Any]:
    """Navigation: „Meine Einsätze“ für Übungsleiter, „Veranstaltungen“ für Abteilungsleitung und Übungsleiter."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    return {
        "is_trainer": services.is_trainer(user),
        "can_plan_events": services.can_plan_staff(user),
        "can_manage_events": services.can_manage_events(user),
    }
