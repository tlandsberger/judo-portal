"""Änderungsprotokoll schreiben und lesen (ADR 0015).

Protokolliert wird ausdrücklich dort, wo etwas geändert wird (Services, Views), nicht über Model-Signale: nur dort ist
bekannt, wer handelt. Bezüge sind Mitglied, Benutzer oder Gast als ID; ``changes`` hält Felder alt → neu.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from django.db import models
from django.db.models import Q, QuerySet
from django.utils import timezone

from .models import Area, AuditEntry

KEEP_DAYS = 365
DELETED_USER = "gelöschter Benutzer"

__all__ = ["Area", "AuditEntry", "diff", "log", "snapshot"]


def _name(actor: Any) -> str:
    if actor is None or not getattr(actor, "is_authenticated", False):
        return ""
    return str(getattr(actor, "display_name", "") or actor)


def _plain(value: Any) -> Any:
    """Werte für JSON: Datum als TT.MM.JJJJ, Decimal als Text, Listen und Model-Objekte als Text."""
    if value is None or isinstance(value, bool | int | str):
        return value
    if isinstance(value, datetime):
        return timezone.localtime(value).strftime("%d.%m.%Y %H:%M")
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Iterable):
        return ", ".join(str(item) for item in value)
    return str(value)


def log(
    actor: Any,
    area: Area | str,
    action: str,
    summary: str,
    *,
    member: Any = None,
    user: Any = None,
    guest: Any = None,
    changes: dict[str, Any] | None = None,
) -> AuditEntry:
    """Einen Eintrag schreiben. ``actor`` ist der handelnde Benutzer, ``None`` für automatische Jobs."""
    return AuditEntry.objects.create(
        actor=actor if _name(actor) else None,
        actor_name=_name(actor)[:200],
        area=str(area),
        action=action[:40],
        summary=summary[:300],
        member_id=getattr(member, "pk", member),
        user_id=getattr(user, "pk", user),
        guest_id=getattr(guest, "pk", guest),
        changes=changes or {},
    )


def snapshot(instance: models.Model, fields: Iterable[str]) -> dict[str, Any]:
    """Lesbare Werte der Felder (Auswahl-Felder mit Anzeige-Text, m:n als Liste) für ``diff``."""
    values: dict[str, Any] = {}
    for name in fields:
        field = instance._meta.get_field(name)
        if field.many_to_many:
            values[name] = sorted(str(item) for item in getattr(instance, name).all()) if instance.pk else []
        elif getattr(field, "choices", None):
            values[name] = getattr(instance, f"get_{name}_display")() if getattr(instance, name) else ""
        else:
            values[name] = getattr(instance, name)
    return values


def diff(before: dict[str, Any], after: dict[str, Any], labels: dict[str, str] | None = None) -> dict[str, Any]:
    """Geänderte Felder als ``{Feldname: [alt, neu]}`` mit lesbaren Namen."""
    labels = labels or {}
    changed = {}
    for name, new in after.items():
        old = before.get(name)
        if _plain(old) != _plain(new):
            changed[labels.get(name, name)] = [_plain(old), _plain(new)]
    return changed


def labels_for(model: type[models.Model], fields: Iterable[str]) -> dict[str, str]:
    return {name: str(getattr(model._meta.get_field(name), "verbose_name", name)) for name in fields}


# Lesen


def entries(
    *,
    area: str | None = None,
    member_id: int | None = None,
    user_id: int | None = None,
    since: date | None = None,
    until: date | None = None,
) -> QuerySet[AuditEntry]:
    rows = AuditEntry.objects.all()
    if area:
        rows = rows.filter(area=area)
    if member_id:
        rows = rows.filter(member_id=member_id)
    if user_id:
        rows = rows.filter(Q(user_id=user_id) | Q(actor_id=user_id))
    if since:
        rows = rows.filter(at__date__gte=since)
    if until:
        rows = rows.filter(at__date__lte=until)
    return rows


# Aufräumen


def forget_member(member_id: int) -> int:
    return AuditEntry.objects.filter(member_id=member_id).delete()[0]


def forget_guest(guest_id: int) -> int:
    return AuditEntry.objects.filter(guest_id=guest_id).delete()[0]


def forget_user(user_id: int) -> None:
    """Gelöschter Benutzer: Einträge über ihn löschen, als Handelnder bleibt nur „gelöschter Benutzer“."""
    AuditEntry.objects.filter(user_id=user_id, member_id__isnull=True).delete()
    AuditEntry.objects.filter(actor_id=user_id).update(actor=None, actor_name=DELETED_USER)
    AuditEntry.objects.filter(user_id=user_id).update(user_id=None)


def cleanup(now: datetime | None = None) -> int:
    """Einträge nach einem Jahr löschen (nächtlicher Job)."""
    limit = (now or timezone.now()) - timedelta(days=KEEP_DAYS)
    return AuditEntry.objects.filter(at__lt=limit).delete()[0]
