from __future__ import annotations

import re
from typing import Any

from django.conf import settings
from django.http import HttpRequest

from portal.accounts.permissions import can_manage_users


def version_url(version: str) -> str:
    """Link zu den Release-Notes der laufenden Version; bei Entwicklungsständen zur Release-Übersicht."""
    if re.fullmatch(r"\d+\.\d+\.\d+", version):
        return f"{settings.RELEASES_URL}/tag/v{version}"
    return settings.RELEASES_URL


def portal(request: HttpRequest) -> dict[str, Any]:
    user = getattr(request, "user", None)
    return {
        "club_name": "Wedeler TSV e.V. – Abteilung Judo",
        "club_short": "Wedeler TSV · Judo",
        "club_email": "judo@wedeler-tsv.de",
        "club_website": "https://www.wedeler-tsv.de/sportangebote-judo/",
        "portal_version": settings.VERSION,
        "portal_version_url": version_url(settings.VERSION),
        "can_manage_users": bool(user and can_manage_users(user)),
    }
