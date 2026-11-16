from __future__ import annotations

from typing import Any

from django import template

from .. import services

register = template.Library()


@register.simple_tag
def pending_claims_count(user: Any) -> int:
    """Für die Startseite: eingereichte Abrechnungen, die die Abteilungsleitung noch prüfen muss."""
    return services.pending_claims().count() if services.can_decide(user) else 0
