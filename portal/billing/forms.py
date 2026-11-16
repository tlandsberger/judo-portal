from __future__ import annotations

from typing import Any

from django import forms
from django.utils import timezone

from portal.events.models import ParticipantRole
from portal.members.forms import DateInput

from .models import Claim, ClaimStatus, Rate


class RateForm(forms.ModelForm):
    """Neuer Satz für eine Rolle. Erhöhungen trägst du mit neuem „gültig ab“ ein, alte Monate bleiben unverändert."""

    class Meta:
        model = Rate
        fields = ("role", "hourly_rate", "valid_from")
        widgets = {"valid_from": DateInput()}

    def __init__(self, *args: Any, roles: list[ParticipantRole], **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["role"].queryset = ParticipantRole.objects.filter(pk__in=[role.pk for role in roles])  # type: ignore[attr-defined]
        self.fields["valid_from"].initial = timezone.localdate().replace(day=1)
        self.fields["hourly_rate"].widget.attrs.update({"step": "0.01", "inputmode": "decimal"})

    def clean(self) -> dict[str, Any]:
        data = super().clean() or {}
        role, valid_from = data.get("role"), data.get("valid_from")
        rates = Rate.objects.filter(member=self.instance.member)
        if role and valid_from and rates.filter(role=role, valid_from=valid_from).exists():
            self.add_error("valid_from", "Für diese Rolle gibt es ab diesem Tag schon einen Satz.")
        return data


class SendBackForm(forms.Form):
    feedback = forms.CharField(
        label="Rückmeldung",
        widget=forms.Textarea(attrs={"rows": 3}),
        max_length=1000,
        help_text="Was soll der Übungsleiter ändern?",
    )


class ClaimFilterForm(forms.Form):
    month = forms.TypedChoiceField(label="Monat", required=False)
    status = forms.ChoiceField(label="Status", required=False, choices=[("", "alle"), *ClaimStatus.choices])

    def __init__(self, *args: Any, months: list[Any], **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["month"].choices = [("", "alle")] + [  # type: ignore[attr-defined]
            (f"{month:%Y-%m}", Claim(month=month).month_label) for month in months
        ]
