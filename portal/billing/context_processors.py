from __future__ import annotations

from typing import Any

from django.http import HttpRequest

from . import services


def billing(request: HttpRequest) -> dict[str, Any]:
    """Navigation: „Abrechnung“ für Übungsleiter (über ``can_join_team`` aus events) und die Abteilungsleitung."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    return {"can_decide_claims": services.can_decide(user)}
