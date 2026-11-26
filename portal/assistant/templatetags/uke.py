"""Antworten von Uke anzeigen: Text sicher maskiert, dazu nur **fett**, einfache Listen („- …“) und Termine, die
die Antwort mit ihrer Marke [T12] nennt, als kleiner Link „Termin →“ (die Links prüft services.resolve_markers
vor dem Speichern)."""

from __future__ import annotations

import re

from django import template
from django.utils.html import escape
from django.utils.safestring import SafeString, mark_safe

register = template.Library()
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITEM = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
_MARKER = re.compile(r"\[(T\d+)\]")


@register.filter
def uke_text(value: str, links: list[dict[str, str]] | None = None) -> SafeString:
    refs = {link["ref"]: link for link in links or [] if link.get("ref")}

    def marker(match: re.Match[str]) -> str:
        link = refs.get(match.group(1))
        if link is None:
            return ""
        # Titel und Zeit stehen schon im Text: hier nur ein kleiner Link, für Screenreader mit vollem Namen
        return (
            f'<a class="badge badge-sm badge-outline whitespace-nowrap no-underline" href="{escape(link["url"])}" '
            f'aria-label="Termin öffnen: {escape(link["label"])}">Termin <i class="bi bi-arrow-right" '
            'aria-hidden="true"></i></a>'
        )

    def _inline(line: str) -> str:
        return _MARKER.sub(marker, _BOLD.sub(r"<strong>\1</strong>", escape(line)))

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
