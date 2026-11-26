"""Antworten von Uke anzeigen: Text sicher maskiert, dazu nur **fett** und einfache Listen („- …“)."""

from __future__ import annotations

import re

from django import template
from django.utils.html import escape
from django.utils.safestring import SafeString, mark_safe

register = template.Library()
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITEM = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")


def _inline(line: str) -> str:
    return _BOLD.sub(r"<strong>\1</strong>", escape(line))


@register.filter
def uke_text(value: str) -> SafeString:
    parts: list[str] = []
    items: list[str] = []
    paragraph: list[str] = []

    def flush() -> None:
        if paragraph:
            parts.append("<p>" + "<br>".join(paragraph) + "</p>")
            paragraph.clear()
        if items:
            parts.append('<ul class="list-disc ps-5">' + "".join(f"<li>{item}</li>" for item in items) + "</ul>")
            items.clear()

    for line in str(value).splitlines():
        if not line.strip():
            flush()
        elif _ITEM.match(line):
            if paragraph:
                flush()
            items.append(_inline(_ITEM.sub("", line, count=1)))
        else:
            if items:
                flush()
            paragraph.append(_inline(line.strip()))
    flush()
    return mark_safe("".join(parts))  # noqa: S308 – alles oben maskiert
