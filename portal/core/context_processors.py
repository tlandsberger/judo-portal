from __future__ import annotations

from typing import Any

from django.http import HttpRequest

from portal.accounts.permissions import can_manage_accounts


def portal(request: HttpRequest) -> dict[str, Any]:
    user = getattr(request, "user", None)
    return {
        "club_name": "Wedeler TSV e.V. – Abteilung Judo",
        "club_short": "Wedeler TSV · Judo",
        "club_email": "judo@wedeler-tsv.de",
        "club_website": "https://www.wedeler-tsv.de/sportangebote-judo/",
        "can_manage_accounts": bool(user and can_manage_accounts(user)),
    }
