from __future__ import annotations

from typing import Any

from django.http import HttpRequest

from . import services


def members(request: HttpRequest) -> dict[str, Any]:
    """Navigation: Mitglieder für die Abteilungsleitung, „Meine Daten“ nur mit verknüpften Mitgliedern."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    return {
        "can_manage_members": services.can_manage_members(user),
        "has_own_members": bool(services.effective_links(user)),
    }
