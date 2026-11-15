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


ALLOWED_DURING_SETUP = {
    "accept_invitation",
    "setup_login",
    "setup_login_by_code",
    "mfa_add_webauthn",
    "mfa_reauthenticate_webauthn",
    "account_set_password",
    "account_logout",
    "healthz",
    "manifest",
    "service_worker",
    "offline",
}


class SetupSessionMiddleware:
    """Einrichtungs-Sitzung nach dem Klick auf einen Einladungslink.

    Bis ein Passkey oder Passwort eingerichtet ist, sind nur die Einrichtungsseiten erreichbar. So bekommt ein
    Mail-Scanner, der den Link öffnet und „Einladung annehmen“ klickt, keinen Zugang zum Portal.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        from django.contrib import messages
        from django.contrib.auth import logout
        from django.shortcuts import redirect
        from django.urls import resolve
        from django.utils import timezone

        from . import services

        session = getattr(request, "session", None)
        user = getattr(request, "user", None)
        state = session.get(services.SETUP_SESSION_KEY) if session is not None else None
        if session is None or not state or user is None or not user.is_authenticated:
            return self.get_response(request)

        if state.get("completed"):
            # In dieser Sitzung wurde ein Passkey oder Passwort angelegt: volle Sitzung, Einladung eingelöst.
            services.complete_invitations(user)
            del session[services.SETUP_SESSION_KEY]
            return self.get_response(request)

        if services.has_login_method(user):
            # Der Zugang wurde in einer anderen Sitzung eingerichtet (z. B. diese hier gehört einem Mail-Scanner).
            logout(request)
            messages.info(request, "Dein Zugang ist bereits eingerichtet. Bitte melde dich an.")
            return redirect("account_login")

        if timezone.now().timestamp() - state.get("started", 0) > services.SETUP_MINUTES * 60:
            logout(request)
            messages.info(
                request, "Die Einrichtung ist abgelaufen. Öffne den Link aus der Einladung bitte noch einmal."
            )
            return redirect("account_login")

        if request.path.startswith(settings.STATIC_URL):
            return self.get_response(request)
        try:
            url_name = resolve(request.path_info).url_name
        except Exception:
            url_name = None
        if url_name not in ALLOWED_DURING_SETUP:
            return redirect("setup_login")
        return self.get_response(request)
