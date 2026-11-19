from __future__ import annotations

from typing import Any

from django import template

from .. import child_access

register = template.Library()


@register.simple_tag
def own_access_offers(user: Any) -> list[Any]:
    """Für die Startseite: Kinder ab 14, für die Eltern einen eigenen Zugang einrichten können (ADR 0024)."""
    return child_access.banner_children(user)
