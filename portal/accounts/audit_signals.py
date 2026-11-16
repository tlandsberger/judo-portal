"""Anmeldewege und Sitzungen ins Änderungsprotokoll (ADR 0015), über die Signale von allauth."""

from __future__ import annotations

from typing import Any

from portal.core import audit


def _log(user: Any, action: str, summary: str) -> None:
    if user is not None and getattr(user, "pk", None):
        audit.log(user, audit.Area.LOGIN, action, summary, user=user)


def password_set(sender: object, request: object = None, user: Any = None, **kwargs: object) -> None:
    _log(user, "password_set", "Passwort gesetzt")


def password_changed(sender: object, request: object = None, user: Any = None, **kwargs: object) -> None:
    _log(user, "password_changed", "Passwort geändert")


def password_reset(sender: object, request: object = None, user: Any = None, **kwargs: object) -> None:
    _log(user, "password_reset", "Passwort zurückgesetzt")


def email_changed(
    sender: object, request: object = None, user: Any = None, from_email_address: Any = None, **kwargs: object
) -> None:
    to = kwargs.get("to_email_address")
    old = getattr(from_email_address, "email", "")
    new = getattr(to, "email", "")
    if user is not None:
        audit.log(user, audit.Area.LOGIN, "email", "E-Mail-Adresse geändert", user=user, changes={"E-Mail": [old, new]})


def _authenticator_name(authenticator: Any) -> str:
    try:
        return str(authenticator.wrap().name)
    except Exception:
        return ""


def authenticator_added(sender: object, request: object = None, user: Any = None, **kwargs: Any) -> None:
    name = _authenticator_name(kwargs.get("authenticator"))
    _log(user, "passkey_added", f"Passkey hinzugefügt{f': {name}' if name else ''}")


def authenticator_removed(sender: object, request: object = None, user: Any = None, **kwargs: Any) -> None:
    name = _authenticator_name(kwargs.get("authenticator"))
    _log(user, "passkey_removed", f"Passkey entfernt{f': {name}' if name else ''}")


def logged_out(sender: object, request: object = None, user: Any = None, **kwargs: object) -> None:
    _log(user, "logout", "Abgemeldet")


def connect() -> None:
    from allauth.account import signals as account
    from allauth.mfa import signals as mfa

    account.password_set.connect(password_set, dispatch_uid="audit_password_set")
    account.password_changed.connect(password_changed, dispatch_uid="audit_password_changed")
    account.password_reset.connect(password_reset, dispatch_uid="audit_password_reset")
    account.email_changed.connect(email_changed, dispatch_uid="audit_email_changed")
    mfa.authenticator_added.connect(authenticator_added, dispatch_uid="audit_authenticator_added")
    mfa.authenticator_removed.connect(authenticator_removed, dispatch_uid="audit_authenticator_removed")
    from django.contrib.auth.signals import user_logged_out

    user_logged_out.connect(logged_out, dispatch_uid="audit_logged_out")
