"""Hilfen für das Seitenlayout (``layouts/page.html``, ADR 0017)."""

from __future__ import annotations

from django import template
from django.template.base import Node, NodeList, Parser, Token
from django.template.context import Context
from django.utils.safestring import mark_safe

register = template.Library()


class CaptureNode(Node):
    # Damit {% block %} innerhalb von {% capture %} in abgeleiteten Templates überschreibbar bleibt.
    child_nodelists = ("nodelist",)

    def __init__(self, nodelist: NodeList, name: str) -> None:
        self.nodelist = nodelist
        self.name = name

    def render(self, context: Context) -> str:
        output = self.nodelist.render(context).strip()
        context[self.name] = mark_safe(output) if output else ""  # noqa: S308 – gerendertes Template
        return ""


@register.tag
def capture(parser: Parser, token: Token) -> CaptureNode:
    """``{% capture as name %}…{% endcapture %}``: Inhalt rendern und als Variable ablegen; nur Leerraum ergibt "".

    So erkennt das Layout, ob eine Seite z. B. eine Hauptaktion oder Menüpunkte füllt.
    """
    bits = token.split_contents()
    if len(bits) != 3 or bits[1] != "as":
        raise template.TemplateSyntaxError("Verwendung: {% capture as name %}…{% endcapture %}")
    nodelist = parser.parse(("endcapture",))
    parser.delete_first_token()
    return CaptureNode(nodelist, bits[2])
