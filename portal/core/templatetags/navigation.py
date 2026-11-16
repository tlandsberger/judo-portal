from __future__ import annotations

from typing import Any

from django import template

from portal.core import navigation

register = template.Library()


@register.simple_tag(takes_context=True)
def menu(context: Any, where: str = "sidebar") -> list[navigation.Group]:
    """Hauptmenü für die Seitenleiste (``sidebar``) oder die Kacheln der Startseite (``tiles``)."""
    result = []
    for group in navigation.groups(context):
        items = [item for item in group.items if (item.tile if where == "tiles" else item.sidebar)]
        if items:
            result.append(navigation.Group(group.title, items))
    return result


@register.filter
def active_for(item: navigation.Item, url_name: str | None) -> bool:
    return item.is_active(url_name)
