"""Rechte für Ansichten. Fachliche Autorisierung liegt immer auf dem Server."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse

from .models import Role

# Wer Konten verwalten (einladen, Rollen ändern) darf.
MANAGE_ACCOUNTS = (Role.DEPARTMENT_HEAD, Role.ADMIN)


def role_required(*roles: Role) -> Callable[[Callable[..., HttpResponse]], Callable[..., HttpResponse]]:
    def decorator(view: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
        @login_required
        @wraps(view)
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            if not request.user.has_role(*roles):  # type: ignore[union-attr]
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


def can_manage_accounts(user: Any) -> bool:
    return bool(user.is_authenticated and user.has_role(*MANAGE_ACCOUNTS))
