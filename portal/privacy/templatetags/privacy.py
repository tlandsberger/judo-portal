from __future__ import annotations

from typing import Any

from django import template

register = template.Library()


@register.filter
def datatype(value: Any) -> str:
    """Für die Darstellung der Auskunft: „dict“, „list“ oder „value“."""
    if isinstance(value, dict):
        return "dict"
    if isinstance(value, list):
        return "list" if any(isinstance(item, dict | list) for item in value) else "flat"
    return "value"


@register.filter
def show(value: Any) -> str:
    if value is True:
        return "ja"
    if value is False:
        return "nein"
    if value in (None, ""):
        return "–"
    return str(value)


@register.filter
def get_item(mapping: Any, key: str) -> Any:
    return mapping.get(key) if isinstance(mapping, dict) else None


@register.simple_tag
def deleted_soon() -> list[Any]:
    """Für die Mitgliederliste: wer in den nächsten 30 Tagen gelöscht wird (Mitglied, Datum)."""
    from portal.privacy import services

    return services.deleted_soon()


@register.simple_tag
def deletion_date(member: Any) -> Any:
    from portal.privacy import services

    return services.deletion_date(member)
