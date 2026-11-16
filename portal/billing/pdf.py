"""PDF einer freigegebenen Abrechnung für die Geschäftsstelle (fpdf2, Kernschrift mit cp1252; ADR 0014)."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.utils import formats, timezone
from fpdf import FPDF

from .models import Claim

LOGO = settings.BASE_DIR / "portal" / "static" / "img" / "logo" / "logo-schwarz.png"


def _euro(value: Decimal) -> str:
    return f"{formats.number_format(value, 2, force_grouping=True)} €"


def _when(moment: object) -> str:
    return formats.date_format(timezone.localtime(moment), "d.m.Y H:i") if moment else "–"  # type: ignore[arg-type]


def render(claim: Claim) -> bytes:
    pdf = FPDF(format="A4")
    pdf.core_fonts_encoding = "windows-1252"  # Umlaute, € und Gedankenstrich mit der eingebauten Helvetica
    pdf.set_title(f"Übungsleiterabrechnung {claim.month_label} – {claim.member.display_name}")
    pdf.set_author("Wedeler TSV Judo")
    pdf.set_margins(18, 18, 18)
    pdf.set_auto_page_break(True, margin=20)
    pdf.add_page()
    if LOGO.exists():
        pdf.image(str(LOGO), x=pdf.w - 18 - 30, y=14, w=30)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 8, "Wedeler TSV Judo", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 13)
    pdf.cell(0, 8, f"Übungsleiterabrechnung {claim.month_label}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("Helvetica", "", 10)
    facts = [
        ("Übungsleiter", claim.member.display_name),
        ("Mitgliedsnummer", claim.member.member_number or "–"),
        ("Eingereicht am", _when(claim.submitted_at) + (" (nach der Frist, Ausnahme)" if claim.is_late else "")),
        ("Freigegeben", f"{_when(claim.decided_at)} von {claim.decided_by_name or '–'}"),
    ]
    for label, value in facts:
        pdf.cell(40, 6, label)
        pdf.cell(0, 6, value, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    with pdf.table(
        col_widths=(22, 64, 30, 18, 20, 20),
        text_align=("LEFT", "LEFT", "LEFT", "RIGHT", "RIGHT", "RIGHT"),
        line_height=6,
        first_row_as_headings=True,
    ) as table:
        table.row(("Datum", "Veranstaltung", "Rolle", "Minuten", "Satz", "Betrag"))
        for line in claim.lines.all():
            table.row(
                (
                    f"{line.day:%d.%m.%Y}",
                    line.event_title,
                    line.role_name,
                    str(line.minutes),
                    _euro(line.hourly_rate),
                    _euro(line.amount),
                )
            )
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 10)
    hours = formats.number_format(claim.hours, 2)
    pdf.cell(0, 6, f"Summe: {hours} Stunden, {_euro(claim.total_amount)}", align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(18)
    pdf.set_font("Helvetica", "", 9)
    width = (pdf.w - 36 - 10) / 2
    y = pdf.get_y()
    pdf.line(18, y, 18 + width, y)
    pdf.line(18 + width + 10, y, pdf.w - 18, y)
    pdf.cell(width + 10, 5, "Datum, Unterschrift Übungsleiter")
    pdf.cell(width, 5, "Geprüft Geschäftsstelle", new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
