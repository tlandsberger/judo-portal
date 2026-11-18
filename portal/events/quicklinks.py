"""Schnellzugang zu Terminen und Veranstaltungen: Code, Quick-Link und QR-Code (ADR 0020).

Der Code steht z. B. auf einer Ausschreibung. Wer ihn eingibt oder den QR-Code scannt, landet nach dem Login direkt
beim Termin bzw. bei den Terminen der Veranstaltung und kann sich dort anmelden.
"""

from __future__ import annotations

import io
import re
import secrets

import segno
from django.conf import settings
from django.db import IntegrityError, transaction
from django.urls import reverse

from .models import Event, Occurrence, QuickLink

ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"  # ohne 0/O, 1/I/L – leicht abzutippen
LENGTH = 6


def _new_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(LENGTH))


def normalize(code: str) -> str:
    """Groß-/Kleinschreibung, Leerzeichen und Bindestriche spielen keine Rolle."""
    return re.sub(r"[\s-]", "", code or "").upper()


def code_for(target: Event | Occurrence) -> str:
    """Code eines Termins oder einer Veranstaltung; beim ersten Aufruf wird er angelegt."""
    field = "event" if isinstance(target, Event) else "occurrence"
    existing = QuickLink.objects.filter(**{field: target}).first()
    if existing:
        return existing.code
    for _ in range(10):
        try:
            with transaction.atomic():
                return QuickLink.objects.create(code=_new_code(), **{field: target}).code
        except IntegrityError:
            existing = QuickLink.objects.filter(**{field: target}).first()
            if existing:  # gleichzeitig angelegt
                return existing.code
    raise RuntimeError("Kein freier Code gefunden.")


def resolve(code: str) -> QuickLink | None:
    code = normalize(code)
    if not code:
        return None
    return QuickLink.objects.select_related("event", "occurrence").filter(code=code).first()


def target_url(link: QuickLink) -> str:
    """Ziel nach dem Login: der Termin oder die Termine der Veranstaltung (alle, nicht nur passende)."""
    if link.occurrence_id:
        return reverse("occurrence_detail", args=[link.occurrence_id])
    return f"{reverse('agenda')}?f=1&veranstaltung={link.event_id}"


def url(code: str) -> str:
    """Vollständiger Quick-Link, wie er auf der Ausschreibung und im QR-Code steht."""
    return f"{settings.BASE_URL}{reverse('quick_link', args=[code])}"


def qr(code: str, kind: str) -> bytes:
    """QR-Code des Quick-Links als SVG oder PNG (schwarz auf weiß, damit er gedruckt und im Dunkeln lesbar ist)."""
    buffer = io.BytesIO()
    image = segno.make(url(code), error="m")
    if kind == "svg":
        image.save(
            buffer,
            kind="svg",
            scale=8,
            border=2,
            dark="black",
            light="white",
            xmldecl=False,
            svgclass=None,
            lineclass=None,
        )
    else:
        image.save(buffer, kind="png", scale=12, border=2, dark="black", light="white")
    return buffer.getvalue()
