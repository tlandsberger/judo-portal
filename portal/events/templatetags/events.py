from __future__ import annotations

from typing import Any

from django import template

from portal.members import services as members

from .. import services

register = template.Library()


@register.simple_tag
def next_dates(user: Any, count: int = 3) -> dict[str, Any]:
    """Für die Startseite: die nächsten passenden Termine über alle eigenen Mitglieder, jeder nur einmal."""
    return {"entries": services.next_entries(user, count), "several": len(members.effective_links(user)) > 1}


@register.simple_tag
def open_confirmations(user: Any) -> list[Any]:
    """Für die Startseite: vergangene Termine als Übungsleiter, die noch auf „Stunden bestätigen“ warten."""
    return services.open_confirmations(user)
