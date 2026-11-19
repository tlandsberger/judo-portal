"""Andocken an Abläufe der Benutzerverwaltung (portal.accounts.signals)."""

from __future__ import annotations

from typing import Any

from django.dispatch import receiver

from portal.accounts.signals import email_changed, greeting_requested, invitation_accepted, own_member_requested

from . import services


@receiver(invitation_accepted, dispatch_uid="members_complete_pending_links")
def complete_pending_links(sender: object, invitation: Any, user: Any, **kwargs: object) -> None:
    services.complete_pending_links(invitation, user)


@receiver(greeting_requested, dispatch_uid="members_parents_greeting")
def parents_greeting(sender: object, user: Any = None, invitation: Any = None, **kwargs: object) -> str:
    return services.parents_greeting(user=user, invitation=invitation)


@receiver(own_member_requested, dispatch_uid="members_own_member_name")
def own_member_name(sender: object, user: Any, **kwargs: object) -> str:
    member = services.own_member(user)
    return member.display_name if member else ""


@receiver(email_changed, dispatch_uid="members_sync_email")
def sync_email(sender: object, user: Any, sync_member: bool = False, **kwargs: object) -> None:
    if sync_member:
        services.take_over_email(user)
