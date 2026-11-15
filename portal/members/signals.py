"""Andocken an Abläufe der Benutzerverwaltung (portal.accounts.signals)."""

from __future__ import annotations

from typing import Any

from django.dispatch import receiver

from portal.accounts.signals import invitation_accepted

from . import services


@receiver(invitation_accepted, dispatch_uid="members_complete_pending_links")
def complete_pending_links(sender: object, invitation: Any, user: Any, **kwargs: object) -> None:
    services.complete_pending_links(invitation, user)
