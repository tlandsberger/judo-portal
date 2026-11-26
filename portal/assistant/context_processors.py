from __future__ import annotations

from typing import Any

from django.http import HttpRequest

from . import services


def assistant(request: HttpRequest) -> dict[str, Any]:
    user = getattr(request, "user", None)
    return {"can_use_assistant": bool(user is not None and services.can_use(user))}
