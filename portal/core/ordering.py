"""Reihenfolge von Katalogwerten (Veranstaltungsarten, Rollen, Interessen …) per Pfeil in der Liste.

Die Modelle haben ein Zahlenfeld für die Reihenfolge und sortieren in ``Meta.ordering`` danach. Neue Einträge kommen
ans Ende; beim Verschieben werden die Werte auf 1 … n neu durchnummeriert, damit gleiche Werte (früher 0) verschwinden.
"""

from __future__ import annotations

from django.contrib import messages
from django.db import models, transaction
from django.db.models import Max
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse


def next_position(model: type[models.Model], field: str) -> int:
    """Wert für einen neuen Eintrag am Ende der Liste."""
    return int(model._default_manager.aggregate(top=Max(field))["top"] or 0) + 1


def append(instance: models.Model, field: str) -> None:
    """Beim Anlegen ans Ende stellen, solange keine Reihenfolge gesetzt ist. Aus ``save()`` der Modelle aufrufen."""
    if instance._state.adding and not getattr(instance, field):
        setattr(instance, field, next_position(type(instance), field))


def move(model: type[models.Model], field: str, pk: int, step: int) -> bool:
    """Einen Eintrag um eine Stelle nach oben (-1) oder unten (+1) verschieben. False, wenn er schon am Rand steht."""
    with transaction.atomic():
        current = list(model._default_manager.values_list("pk", flat=True))
        index = current.index(pk)
        target = index + step
        if not 0 <= target < len(current):
            return False
        current[index], current[target] = current[target], current[index]
        objects = model._default_manager.in_bulk(current)
        changed = []
        for position, key in enumerate(current, start=1):
            obj = objects[key]
            if getattr(obj, field) != position:
                setattr(obj, field, position)
                changed.append(obj)
        model._default_manager.bulk_update(changed, [field])
        return True


def handle(request: HttpRequest, model: type[models.Model], field: str, list_url: str) -> HttpResponse:
    """POST der Pfeil-Knöpfe (``up`` bzw. ``down`` mit der ID); zurück zur Liste an die verschobene Zeile."""
    step, value = (-1, request.POST.get("up")) if "up" in request.POST else (1, request.POST.get("down"))
    obj = get_object_or_404(model, pk=value if str(value).isdigit() else None)
    if move(model, field, obj.pk, step):
        messages.success(request, f"„{obj}“ nach {'oben' if step < 0 else 'unten'} verschoben.")
    return redirect(f"{reverse(list_url)}#sort-{obj.pk}")
