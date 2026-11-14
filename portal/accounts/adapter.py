"""Anpassungen an django-allauth."""

from __future__ import annotations

from allauth.account.adapter import DefaultAccountAdapter
from django.http import HttpRequest


class PortalAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest) -> bool:
        # Konten entstehen nur über Einladungen aus dem Portal.
        return False

    def get_login_stages(self) -> list[str]:
        # Passkey, Passwort und Mail-Code sind gleichwertige Anmeldewege: Ein vorhandener Passkey wird nicht
        # als zweiter Faktor erzwungen, sonst käme man mit Passwort oder Code nicht mehr ohne Passkey hinein.
        return [stage for stage in super().get_login_stages() if not stage.startswith("allauth.mfa.stages.")]
