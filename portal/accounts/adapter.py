"""Anpassungen an django-allauth."""

from __future__ import annotations

from typing import Any

from allauth.account.adapter import DefaultAccountAdapter
from django.http import HttpRequest
from django.urls import reverse

from . import services


class PortalAccountAdapter(DefaultAccountAdapter):
    def send_notification_mail(self, template_prefix: str, user: Any, context: Any = None, email: Any = None) -> None:
        # Sicherheitsmails (Passwort, Passkey …) gehen immer per Mail – nur nicht während der Einrichtung nach der
        # Einladung: Da legt die Person ihre Anmeldewege gerade selbst an.
        request = getattr(self, "request", None)
        session = getattr(request, "session", None)
        if session is not None and session.get(services.SETUP_SESSION_KEY):
            return
        super().send_notification_mail(template_prefix, user, context, email)

    def is_open_for_signup(self, request: HttpRequest) -> bool:
        # Benutzer entstehen nur über Einladungen aus dem Portal.
        return False

    def get_login_stages(self) -> list[str]:
        # Passkey, Passwort und Mail-Code sind gleichwertige Anmeldewege: Ein vorhandener Passkey wird nicht
        # als zweiter Faktor erzwungen, sonst käme man mit Passwort oder Code nicht mehr ohne Passkey hinein.
        return [stage for stage in super().get_login_stages() if not stage.startswith("allauth.mfa.stages.")]

    def get_password_change_redirect_url(self, request: HttpRequest) -> str:
        # Statt zurück auf „Passwort ändern“: in der Einrichtung zurück zur Übersicht der Anmeldewege, sonst zu
        # „Meine Anmeldung“.
        if request.session.get(services.SETUP_SESSION_KEY):
            return reverse("setup_login")
        return reverse("security")
