from __future__ import annotations

from typing import Any

from django import template
from django.urls import reverse
from django.utils.html import format_html

from portal.help import chapters

register = template.Library()

THEMES = (("light", ""), ("dark", "-dunkel"))


@register.simple_tag(takes_context=True)
def help_link(context: dict[str, Any], slug: str) -> str:
    """Kleines „?“ neben einer Überschrift, das zum passenden Kapitel führt (nur wenn es sichtbar ist)."""
    request = context.get("request")
    chapter = chapters.get(slug, getattr(request, "user", None)) if request else None
    if chapter is None:
        return ""
    return format_html(
        '<a class="btn btn-ghost btn-circle btn-sm" href="{}" aria-label="Hilfe: {}" title="Hilfe: {}">'
        '<i class="bi bi-question-circle text-lg" aria-hidden="true"></i></a>',
        reverse("help_chapter", args=[chapter.slug]),
        chapter.title,
        chapter.title,
    )


@register.inclusion_tag("help/_figure.html")
def screenshot(name: str, alt: str, caption: str = "", mobile: bool = True) -> dict[str, Any]:
    """Screenshot aus ``static/help/img`` (von ``e2e/hilfe.spec.ts``): Desktop, auf dem Handy die Handy-Ansicht,
    je im hellen und dunklen Theme; angezeigt wird das zum gewählten Theme passende."""
    return {"name": name, "alt": alt, "caption": caption, "mobile": mobile, "themes": THEMES}
