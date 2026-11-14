"""Gleitende Sitzung: „Angemeldet bleiben“ läuft 30 Tage ab der letzten Nutzung."""

from __future__ import annotations

from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse

REFRESH_AFTER = 24 * 60 * 60  # höchstens einmal am Tag in die Datenbank schreiben


class SlidingSessionMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        session = getattr(request, "session", None)
        user = getattr(request, "user", None)
        if (
            session is not None
            and user is not None
            and user.is_authenticated
            and not session.get_expire_at_browser_close()
            and session.get_expiry_age() < settings.SESSION_COOKIE_AGE - REFRESH_AFTER
        ):
            session.set_expiry(settings.SESSION_COOKIE_AGE)
        return response
