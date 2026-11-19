"""Felder nebeneinander: Gruppen aus ``layout`` werden zu Zeilen, fehlende Felder rücken zusammen."""

from __future__ import annotations

from django import forms

from portal.core.templatetags.form_layout import field_rows, rows


class PeriodForm(forms.Form):
    layout = (("start", "end"), ("agree", "count"))

    title = forms.CharField()
    start = forms.DateField()
    note = forms.CharField()
    end = forms.DateField()
    count = forms.IntegerField()
    agree = forms.BooleanField()


def names(result):
    return [[field.name for field in row.fields] for row in result]


def test_groups_stand_where_their_first_field_is():
    result = rows(PeriodForm())
    assert names(result) == [
        ["title"],
        ["start", "end"],
        ["note"],
        ["agree", "count"],
    ]  # Reihenfolge in der Zeile wie in layout
    assert result[1].grid == "grid gap-x-4 sm:grid-cols-2" and result[0].grid == ""
    assert result[3].mixed and not result[1].mixed


def test_subset_and_exclude_close_gaps():
    form = PeriodForm()
    assert names(field_rows(form, [form["end"], form["note"]])) == [["note"], ["end"]]
    assert names(field_rows(form, exclude="title start agree")) == [["note"], ["end"], ["count"]]
