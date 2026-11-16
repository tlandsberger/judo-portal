"""Datenauskunft als PDF (fpdf2, eingebaute Helvetica mit Windows-1252; ADR 0015)."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.utils import timezone
from fpdf import FPDF

LOGO = settings.BASE_DIR / "portal" / "static" / "img" / "logo" / "logo-schwarz.png"
LABEL_WIDTH = 52


def _text(value: Any) -> str:
    """Für die eingebaute Schrift: Ja/Nein, Striche für leer, Zeichen außerhalb von Windows-1252 ersetzen."""
    if value is True:
        value = "ja"
    elif value is False:
        value = "nein"
    elif value in (None, ""):
        value = "–"
    text = str(value).replace("→", "->")
    return text.encode("cp1252", "replace").decode("cp1252")


def _is_scalar(value: Any) -> bool:
    return not isinstance(value, dict | list)


class _Report(FPDF):
    def footer(self) -> None:
        self.set_y(-14)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(110)
        self.cell(0, 6, f"Wedeler TSV Judo – Datenauskunft (Art. 15 DSGVO) – Seite {self.page_no()}", align="C")
        self.set_text_color(0)


def _heading(pdf: FPDF, text: str, level: int) -> None:
    size = {1: 13, 2: 11}.get(level, 10)
    if pdf.get_y() > pdf.h - 40:
        pdf.add_page()
    pdf.ln(3 if level > 1 else 5)
    pdf.set_font("Helvetica", "B", size)
    pdf.multi_cell(0, 6, _text(text), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)


def _pair(pdf: FPDF, label: str, value: Any, indent: float) -> None:
    """Bezeichnung links, Wert rechts. Umbruch vorher, damit beide Spalten auf derselben Seite beginnen."""
    if pdf.get_y() + 12 > pdf.page_break_trigger:
        pdf.add_page()
    y, page = pdf.get_y(), pdf.page_no()
    pdf.set_xy(pdf.l_margin + indent, y)
    pdf.set_font("Helvetica", "B", 9)
    pdf.multi_cell(LABEL_WIDTH, 5, _text(label), new_x="LMARGIN", new_y="NEXT")
    label_bottom = pdf.get_y()
    pdf.set_xy(pdf.l_margin + indent + LABEL_WIDTH, y)
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(0, 5, _text(value), new_x="LMARGIN", new_y="NEXT")
    if pdf.page_no() == page:
        pdf.set_y(max(pdf.get_y(), label_bottom))


def _is_table(rows: list[Any]) -> bool:
    """Gleich aufgebaute Einträge ohne Unterlisten (Teilnahmen, Geräte, Protokoll …) passen in eine Tabelle."""
    if not rows or not all(isinstance(row, dict) for row in rows):
        return False
    keys = list(rows[0])
    return all(list(row) == keys and all(_is_scalar(v) for v in row.values()) for row in rows)


def _table(pdf: FPDF, rows: list[dict[str, Any]], indent: float) -> None:
    keys = list(rows[0])
    # Spaltenbreite nach dem längsten Inhalt (gedeckelt), damit lange Beschreibungen Platz bekommen
    widths = [min(max(len(_text(key)), *(len(_text(row[key])) for row in rows)), 45) + 4 for key in keys]
    pdf.set_font("Helvetica", "", 7 if len(keys) > 5 else 8)
    pdf.set_x(pdf.l_margin + indent)
    with pdf.table(
        width=pdf.w - pdf.l_margin - pdf.r_margin - indent,
        col_widths=widths,
        text_align="LEFT",
        line_height=4,
        first_row_as_headings=True,
        align="LEFT",
    ) as table:
        table.row([_text(key) for key in keys])
        for row in rows:
            table.row([_text(row[key]) for key in keys])
    pdf.set_font("Helvetica", "", 9)
    pdf.ln(2)


def _render(pdf: FPDF, data: Any, indent: float, level: int) -> None:
    if isinstance(data, dict):
        for key, value in data.items():
            if _is_scalar(value):
                _pair(pdf, key, value, indent)
            elif level > 1 and isinstance(value, list) and all(_is_scalar(item) for item in value):
                _pair(pdf, key, ", ".join(_text(item) for item in value) if value else None, indent)
            else:
                _heading(pdf, key, level)
                _render(pdf, value, indent, level + 1)
    elif isinstance(data, list) and _is_table(data):
        _table(pdf, data, indent)
    elif isinstance(data, list):
        if not data:
            pdf.set_x(pdf.l_margin + indent)
            pdf.cell(0, 5, "–", new_x="LMARGIN", new_y="NEXT")
        for item in data:
            if _is_scalar(item):
                pdf.set_x(pdf.l_margin + indent)
                pdf.multi_cell(0, 5, f"• {_text(item)}", new_x="LMARGIN", new_y="NEXT")
                continue
            _render(pdf, item, indent + 4, level)
            pdf.set_draw_color(200)
            pdf.line(pdf.l_margin + indent + 4, pdf.get_y() + 1, pdf.w - pdf.r_margin, pdf.get_y() + 1)
            pdf.set_draw_color(0)
            pdf.ln(3)
    else:
        pdf.set_x(pdf.l_margin + indent)
        pdf.multi_cell(0, 5, _text(data), new_x="LMARGIN", new_y="NEXT")


def render(data: dict[str, Any], subject: str) -> bytes:
    pdf = _Report(format="A4")
    pdf.core_fonts_encoding = "windows-1252"
    pdf.set_title(f"Datenauskunft – {subject}")
    pdf.set_author("Wedeler TSV Judo")
    pdf.set_margins(18, 18, 18)
    pdf.set_auto_page_break(True, margin=20)
    pdf.add_page()
    if LOGO.exists():
        pdf.image(str(LOGO), x=pdf.w - 18 - 30, y=14, w=30)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 8, "Wedeler TSV Judo", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 13)
    pdf.cell(0, 8, _text("Datenauskunft (Art. 15 DSGVO)"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    created = timezone.localtime().strftime("%d.%m.%Y %H:%M")
    pdf.multi_cell(
        0,
        5,
        _text(f"Für: {subject} · erstellt am {created} Uhr. Alle Daten, die das Vereinsportal dazu speichert."),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(2)
    # Erstellt am und Hinweis stehen schon im Kopf
    _render(pdf, {k: v for k, v in data.items() if k not in ("Erstellt am", "Hinweis")}, 0, 1)
    return bytes(pdf.output())
