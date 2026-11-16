from __future__ import annotations

from django import forms

from portal.core.models import Area
from portal.members.forms import DateInput


class AuditFilterForm(forms.Form):
    area = forms.ChoiceField(label="Bereich", required=False, choices=[("", "alle"), *Area.choices])
    q = forms.CharField(label="Suche", required=False, max_length=100)
    since = forms.DateField(label="Von", required=False, widget=DateInput())
    until = forms.DateField(label="Bis", required=False, widget=DateInput())


class DeleteForm(forms.Form):
    confirm = forms.BooleanField(label="Ich habe verstanden, dass die Daten endgültig gelöscht werden.", required=True)
