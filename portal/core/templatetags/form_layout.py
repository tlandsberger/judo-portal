"""Felder eines Formulars in Zeilen: Was zusammengehört (von–bis, Vor- und Nachname), steht ab Tablet-Breite
nebeneinander. Die Formulare nennen die Gruppen in ``layout``; ohne ``layout`` steht jedes Feld in einer Zeile."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django import forms, template

register = template.Library()

# Klassen ausgeschrieben, damit Tailwind sie findet.
GRID = {2: "grid gap-x-4 sm:grid-cols-2", 3: "grid gap-x-4 sm:grid-cols-3"}


@dataclass
class Row:
    fields: list[forms.BoundField]

    @property
    def grid(self) -> str:
        return GRID.get(len(self.fields), "")

    @property
    def mixed(self) -> bool:
        """Checkbox neben einem Eingabefeld: die Checkbox rückt auf Höhe des Feldes (unter dessen Beschriftung)."""
        kinds = {field.widget_type == "checkbox" for field in self.fields}
        return len(self.fields) > 1 and len(kinds) == 2


def rows(form: forms.BaseForm, names: list[str] | None = None) -> list[Row]:
    """Zeilen aus den sichtbaren Feldern (oder nur ``names``, in Formular-Reihenfolge). Eine Gruppe aus ``layout``
    steht dort, wo ihr erstes Feld steht; fehlen Felder der Gruppe, rücken die übrigen zusammen."""
    visible = [field for field in form.visible_fields() if names is None or field.name in names]
    by_name = {field.name: field for field in visible}
    group_of = {name: group for group in getattr(form, "layout", ()) for name in group}
    result: list[Row] = []
    done: set[str] = set()
    for field in visible:
        if field.name in done:
            continue
        group = [by_name[name] for name in group_of.get(field.name, (field.name,)) if name in by_name]
        done.update(member.name for member in group)
        result.append(Row(group))
    return result


@register.simple_tag
def field_rows(form: forms.BaseForm, fields: Any = None, exclude: str = "") -> list[Row]:
    """``{% field_rows form as rows %}``; ``fields``: Liste gebundener Felder, ``exclude``: Namen mit Leerzeichen."""
    names = [field.name for field in fields] if fields is not None else None
    skip = set(exclude.split())
    if skip:
        names = [
            field.name
            for field in form.visible_fields()
            if field.name not in skip and (names is None or field.name in names)
        ]
    return rows(form, names)
