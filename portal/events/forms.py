from __future__ import annotations

from typing import Any

from django import forms

from portal.accounts.models import User
from portal.members.forms import DateInput, WeightInput
from portal.members.models import Gender

from .models import Event, Occurrence, Schedule, StaffFunction, TargetGroup


class DateTimeInput(forms.DateTimeInput):
    input_type = "datetime-local"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(format="%Y-%m-%dT%H:%M", **kwargs)


class TimeInput(forms.TimeInput):
    input_type = "time"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(format="%H:%M", **kwargs)


class TargetGroupForm(forms.ModelForm):
    genders = forms.MultipleChoiceField(
        label="Geschlecht",
        choices=Gender.choices,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Nichts ausgewählt heißt: alle.",
    )

    class Meta:
        model = TargetGroup
        fields = (
            "name",
            "description",
            "min_age",
            "max_age",
            "genders",
            "min_weight",
            "max_weight",
            "min_grade",
            "max_grade",
            "interests",
        )
        localized_fields = ("min_weight", "max_weight")
        widgets = {
            "min_weight": WeightInput(),
            "max_weight": WeightInput(),
            "interests": forms.CheckboxSelectMultiple(),
        }

    def clean(self) -> dict[str, Any]:
        data = super().clean() or {}
        for low, high, label in (("min_age", "max_age", "Alter"), ("min_weight", "max_weight", "Gewicht")):
            if data.get(low) is not None and data.get(high) is not None and data[low] > data[high]:
                self.add_error(high, f"{label} bis muss mindestens {label} ab sein.")
        return data


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = (
            "title",
            "kind",
            "description",
            "location",
            "target_groups",
            "capacity",
            "weight_required",
            "registration_opens_at",
            "registration_closes_at",
            "opens_days_before",
            "closes_hours_before",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "target_groups": forms.CheckboxSelectMultiple(),
            "registration_opens_at": DateTimeInput(),
            "registration_closes_at": DateTimeInput(),
        }
        help_texts = {
            "registration_opens_at": "Für einmalige Veranstaltungen. Leer heißt: sofort.",
            "registration_closes_at": "Für einmalige Veranstaltungen. Leer heißt: bis zum Beginn.",
        }


class ScheduleForm(forms.ModelForm):
    class Meta:
        model = Schedule
        fields = ("weekday", "start_time", "end_time", "valid_from", "valid_until")
        widgets = {
            "start_time": TimeInput(),
            "end_time": TimeInput(),
            "valid_from": DateInput(),
            "valid_until": DateInput(),
        }

    def clean(self) -> dict[str, Any]:
        data = super().clean() or {}
        if data.get("start_time") and data.get("end_time") and data["end_time"] <= data["start_time"]:
            self.add_error("end_time", "Das Ende muss nach dem Beginn liegen.")
        if data.get("valid_from") and data.get("valid_until") and data["valid_until"] < data["valid_from"]:
            self.add_error("valid_until", "„Gültig bis“ muss nach „Gültig ab“ liegen.")
        return data


class OccurrenceForm(forms.ModelForm):
    """Termin von Hand (einmalig oder zusätzlich) bzw. Abweichung an einem Termin."""

    class Meta:
        model = Occurrence
        fields = ("starts_at", "ends_at", "location", "note")
        widgets = {"starts_at": DateTimeInput(), "ends_at": DateTimeInput()}
        labels = {"location": "Ort (falls abweichend)"}

    def clean(self) -> dict[str, Any]:
        data = super().clean() or {}
        if data.get("starts_at") and data.get("ends_at") and data["ends_at"] <= data["starts_at"]:
            self.add_error("ends_at", "Das Ende muss nach dem Beginn liegen.")
        return data


class NoteForm(forms.ModelForm):
    class Meta:
        model = Occurrence
        fields = ("note",)


class CancelRangeForm(forms.Form):
    first = forms.DateField(label="Von", widget=DateInput())
    last = forms.DateField(label="Bis", widget=DateInput())

    def clean(self) -> dict[str, Any]:
        data = super().clean() or {}
        if data.get("first") and data.get("last") and data["last"] < data["first"]:
            self.add_error("last", "„Bis“ muss nach „Von“ liegen.")
        return data


class RegisterForm(forms.Form):
    weight = forms.DecimalField(
        label="Gewicht (kg)",
        max_digits=4,
        decimal_places=1,
        min_value=10,
        max_value=250,
        localize=True,
        widget=WeightInput(),
        help_text="Wird auch als aktuelles Gewicht in „Meine Daten“ übernommen.",
    )
    note = forms.CharField(label="Hinweis", max_length=200, required=False, help_text="Zum Beispiel „komme später“.")

    def __init__(self, *args: Any, weight_required: bool, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if not weight_required:
            del self.fields["weight"]


class StaffForm(forms.Form):
    user = forms.ModelChoiceField(label="Übungsleiter", queryset=User.objects.none())
    function = forms.ChoiceField(label="Funktion", choices=StaffFunction.choices)

    def __init__(self, *args: Any, trainers: list[User], **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        field = self.fields["user"]
        field.queryset = User.objects.filter(pk__in=[trainer.pk for trainer in trainers])  # type: ignore[attr-defined]
        field.label_from_instance = lambda user: user.display_name  # type: ignore[attr-defined]


class ConfirmForm(forms.Form):
    minutes = forms.IntegerField(label="Dauer (Minuten)", min_value=1, max_value=24 * 60)
