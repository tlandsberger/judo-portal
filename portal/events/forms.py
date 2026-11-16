from __future__ import annotations

from typing import Any

from django import forms
from django.db import models
from django.utils import timezone

from portal.accounts.models import Role
from portal.members.forms import DateInput, WeightInput
from portal.members.models import Gender, Member

from .models import Event, EventType, Occurrence, ParticipantRole, Schedule, TargetGroup, Weekday


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
        fields = ("title", "event_type", "description", "location", "target_groups", "capacity", "weight_required")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "target_groups": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        current = self.instance.event_type_id if self.instance.pk else None
        field = self.fields["event_type"]
        field.queryset = EventType.objects.filter(models.Q(is_active=True) | models.Q(pk=current))  # type: ignore[attr-defined]
        field.empty_label = None  # type: ignore[attr-defined]


class EventCreateForm(EventForm):
    """Veranstaltung anlegen und gleich die Termine festlegen: einmalig, wiederkehrend oder später (ADR 0012)."""

    ONCE, WEEKLY, LATER = "once", "weekly", "later"

    dates = forms.ChoiceField(
        label="Termine",
        choices=[(ONCE, "Einmalig"), (WEEKLY, "Wiederkehrend"), (LATER, "Später festlegen")],
        initial=ONCE,
        widget=forms.RadioSelect,
    )
    starts_at = forms.DateTimeField(label="Beginn", required=False, widget=DateTimeInput())
    ends_at = forms.DateTimeField(
        label="Ende", required=False, widget=DateTimeInput(), help_text="Auch über mehrere Tage, z. B. Lehrgang Sa–So."
    )
    registration_opens_at = forms.DateTimeField(
        label="Anmeldung ab", required=False, widget=DateTimeInput(), help_text="Leer heißt: sofort."
    )
    registration_closes_at = forms.DateTimeField(
        label="Anmeldeschluss", required=False, widget=DateTimeInput(), help_text="Leer heißt: bis zum Beginn."
    )
    weekdays = forms.TypedMultipleChoiceField(
        label="Wochentage",
        choices=Weekday.choices,
        coerce=int,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Je Wochentag entsteht ein Zeitplan.",
    )
    start_time = forms.TimeField(label="Uhrzeit von", required=False, widget=TimeInput())
    end_time = forms.TimeField(label="Uhrzeit bis", required=False, widget=TimeInput())
    valid_from = forms.DateField(label="Gültig ab", required=False, widget=DateInput())
    valid_until = forms.DateField(
        label="Gültig bis", required=False, widget=DateInput(), help_text="Leer heißt: bis auf Weiteres."
    )
    opens_hours_before = forms.IntegerField(
        label="Anmeldung öffnet (Stunden vorher)", required=False, min_value=0, help_text="Leer heißt: sofort."
    )
    closes_hours_before = forms.IntegerField(
        label="Anmeldung schließt (Stunden vorher)", required=False, min_value=0, help_text="Leer heißt: zum Beginn."
    )
    team_member = forms.ModelChoiceField(label="Mitglied", queryset=Member.objects.none(), required=False)
    team_role = forms.ModelChoiceField(label="Rolle", queryset=ParticipantRole.objects.none(), required=False)

    ONCE_FIELDS = ("starts_at", "ends_at", "registration_opens_at", "registration_closes_at")
    WEEKLY_FIELDS = (
        "weekdays",
        "start_time",
        "end_time",
        "valid_from",
        "valid_until",
        "opens_hours_before",
        "closes_hours_before",
    )
    TEAM_FIELDS = ("team_member", "team_role")

    def __init__(self, *args: Any, candidates: list[Member], roles: list[ParticipantRole], **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        member = self.fields["team_member"]
        member.queryset = Member.objects.filter(pk__in=[m.pk for m in candidates]).order_by(  # type: ignore[attr-defined]
            "first_name", "last_name"
        )
        member.label_from_instance = lambda m: m.display_name  # type: ignore[attr-defined]
        self.fields["team_role"].queryset = ParticipantRole.objects.filter(  # type: ignore[attr-defined]
            pk__in=[r.pk for r in roles]
        )
        self.fields["valid_from"].initial = timezone.localdate()

    def _group(self, names: tuple[str, ...]) -> list[Any]:
        return [self[name] for name in names]

    @property
    def event_fields(self) -> list[Any]:
        extra = {"dates", *self.ONCE_FIELDS, *self.WEEKLY_FIELDS, *self.TEAM_FIELDS}
        return [self[name] for name in self.fields if name not in extra]

    @property
    def once_fields(self) -> list[Any]:
        return self._group(self.ONCE_FIELDS)

    @property
    def weekly_fields(self) -> list[Any]:
        return self._group(self.WEEKLY_FIELDS)

    @property
    def team_fields(self) -> list[Any]:
        return self._group(self.TEAM_FIELDS)

    def clean(self) -> dict[str, Any]:
        data = super().clean() or {}
        mode = data.get("dates")
        required: tuple[str, ...] = ()
        if mode == self.ONCE:
            required = ("starts_at", "ends_at")
            if data.get("starts_at") and data.get("ends_at") and data["ends_at"] <= data["starts_at"]:
                self.add_error("ends_at", "Das Ende muss nach dem Beginn liegen.")
            opens, closes = data.get("registration_opens_at"), data.get("registration_closes_at")
            if opens and closes and closes <= opens:
                self.add_error("registration_closes_at", "Der Anmeldeschluss muss nach dem Anmeldebeginn liegen.")
        elif mode == self.WEEKLY:
            required = ("weekdays", "start_time", "end_time", "valid_from")
            if data.get("start_time") and data.get("end_time") and data["end_time"] <= data["start_time"]:
                self.add_error("end_time", "Das Ende muss nach dem Beginn liegen.")
            if data.get("valid_from") and data.get("valid_until") and data["valid_until"] < data["valid_from"]:
                self.add_error("valid_until", "„Gültig bis“ muss nach „Gültig ab“ liegen.")
        for name in required:
            if not data.get(name) and name not in self.errors:
                self.add_error(name, "Bitte ausfüllen.")
        if bool(data.get("team_member")) != bool(data.get("team_role")):
            self.add_error("team_role", "Für das Team bitte Mitglied und Rolle wählen – oder beides leer lassen.")
        if mode == self.LATER and data.get("team_member"):
            self.add_error("team_member", "Das Team trägst du ein, sobald es Termine gibt.")
        return data


class ScheduleForm(forms.ModelForm):
    class Meta:
        model = Schedule
        fields = (
            "weekday",
            "start_time",
            "end_time",
            "valid_from",
            "valid_until",
            "opens_hours_before",
            "closes_hours_before",
        )
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
        fields = ("starts_at", "ends_at", "location", "note", "registration_opens_at", "registration_closes_at")
        widgets = {
            "starts_at": DateTimeInput(),
            "ends_at": DateTimeInput(),
            "registration_opens_at": DateTimeInput(),
            "registration_closes_at": DateTimeInput(),
        }
        labels = {"location": "Ort (falls abweichend)"}

    def clean(self) -> dict[str, Any]:
        data = super().clean() or {}
        if data.get("starts_at") and data.get("ends_at") and data["ends_at"] <= data["starts_at"]:
            self.add_error("ends_at", "Das Ende muss nach dem Beginn liegen.")
        opens, closes = data.get("registration_opens_at"), data.get("registration_closes_at")
        if opens and closes and closes <= opens:
            self.add_error("registration_closes_at", "Der Anmeldeschluss muss nach dem Anmeldebeginn liegen.")
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


class TeamForm(forms.Form):
    """Team eines Termins oder Standard-Team eines Zeitplans: Mitglied und Rolle."""

    member = forms.ModelChoiceField(label="Mitglied", queryset=Member.objects.none())
    role = forms.ModelChoiceField(label="Rolle", queryset=ParticipantRole.objects.none())

    def __init__(self, *args: Any, candidates: list[Member], roles: list[ParticipantRole], **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        member = self.fields["member"]
        member.queryset = Member.objects.filter(pk__in=[m.pk for m in candidates]).order_by(  # type: ignore[attr-defined]
            "first_name", "last_name"
        )
        member.label_from_instance = lambda m: m.display_name  # type: ignore[attr-defined]
        self.fields["role"].queryset = ParticipantRole.objects.filter(  # type: ignore[attr-defined]
            pk__in=[r.pk for r in roles]
        )


class EventTypeForm(forms.ModelForm):
    class Meta:
        model = EventType
        fields = ("name", "order", "is_active")


class ParticipantRoleForm(forms.ModelForm):
    user_roles = forms.MultipleChoiceField(
        label="Benutzerrollen",
        choices=[(Role.TRAINER.value, Role.TRAINER.label), (Role.DEPARTMENT_HEAD.value, Role.DEPARTMENT_HEAD.label)],
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Wer die Rolle übernehmen darf (über das eigene Mitgliedsprofil). Nichts ausgewählt heißt: jedes "
        "Mitglied.",
    )

    class Meta:
        model = ParticipantRole
        fields = ("name", "order", "event_types", "user_roles", "is_team", "is_billable", "is_default", "is_active")
        widgets = {"event_types": forms.CheckboxSelectMultiple()}

    def _get_validation_exclusions(self) -> set[str]:
        # Die Markierung „Rolle bei Anmeldung“ setzt die View um (alte Rolle verliert sie im selben Schritt).
        return {*super()._get_validation_exclusions(), "is_default"}  # type: ignore[misc]

    def clean(self) -> dict[str, Any]:
        data = super().clean() or {}
        if data.get("is_default") and not data.get("is_active"):
            self.add_error("is_active", "Die Rolle bei Anmeldung muss aktiv sein.")
        if self.instance.pk and self.instance.is_default and not data.get("is_default"):
            self.add_error("is_default", "Markiere dafür eine andere Rolle als „Rolle bei Anmeldung“.")
        return data


class ConfirmForm(forms.Form):
    minutes = forms.IntegerField(label="Dauer (Minuten)", min_value=1, max_value=24 * 60)
