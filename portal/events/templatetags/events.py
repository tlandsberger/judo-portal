from __future__ import annotations

from typing import Any

from django import template

from .. import services

register = template.Library()


@register.simple_tag
def next_dates(user: Any, count: int = 3) -> list[tuple[Any, services.AgendaItem]]:
    """Für die Startseite: die nächsten passenden Termine über alle eigenen Mitglieder."""
    return services.next_items(user, count)
