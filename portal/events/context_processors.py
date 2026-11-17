from __future__ import annotations

from typing import Any

from django.http import HttpRequest

from . import services


def events(request: HttpRequest) -> dict[str, Any]:
    """Navigation: „Meine Abrechnung“ und „Veranstaltungen“ für Übungsleiter und die Abteilungsleitung."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    return {
        "can_join_team": services.can_join_team(user),
        "can_plan_events": services.can_plan_staff(user),
        "can_manage_events": services.can_manage_events(user),
    }
