from __future__ import annotations

from typing import Any, cast

from django import forms
from django.db import models
from django.utils import formats, timezone

from portal.accounts.models import Role
from portal.members.forms import DateInput, WeightInput
from portal.members.models import Gender, Member

from .models import (
    Event,
    EventType,
    Guest,
    Occurrence,
    OccurrenceTargetGroup,
    ParticipantRole,
    Repeat,
    Schedule,
    TargetGroup,
    TargetGroupTemplate,
    TargetMode,
    Weekday,
    WeekOfMonth,
)
from .services import AgendaFilter


class DateTimeInput(forms.DateTimeInput):
    input_type = "datetime-local"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(format="%Y-%m-%dT%H:%M", **kwargs)


class TimeInput(forms.TimeInput):
    input_type = "time"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(format="%H:%M", **kwargs)


CRITERIA_FIELDS = (
    "min_age",
    "max_age",
    "genders",
    "min_weight",
    "max_weight",
    "min_grade",
    "max_grade",
    "interests",
)
CRITERIA_WIDGETS = {
    "min_weight": WeightInput(),
    "max_weight": WeightInput(),
    "interests": forms.CheckboxSelectMultiple(),
}


class CriteriaForm(forms.ModelForm):
    """Kriterien einer Zielgruppe oder Vorlage, mit Prüfung von/bis."""

    genders = forms.MultipleChoiceField(
        label="Geschlecht",
        choices=Gender.choices,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Nichts ausgewählt heißt: alle.",
    )

    def clean(self) -> dict[str, Any]:
        data = super().clean() or {}
        for low, high, label in (("min_age", "max_age", "Alter"), ("min_weight", "max_weight", "Gewicht")):
            if data.get(low) is not None and data.get(high) is not None and data[low] > data[high]:
                self.add_error(high, f"{label} bis muss mindestens {label} ab sein.")
        return data


class TargetGroupTemplateForm(CriteriaForm):
    class Meta:
        model = TargetGroupTemplate
        fields = ("name", "description", *CRITERIA_FIELDS)
        localized_fields = ("min_weight", "max_weight")
        widgets = CRITERIA_WIDGETS


class TargetGroupForm(CriteriaForm):
    """Ein Zielgruppen-Block im Formular der Veranstaltung; auf Wunsch auch als Vorlage gespeichert."""

    save_as_template = forms.BooleanField(
        label="Als Vorlage speichern",
        required=False,
        help_text="Dann kannst du die Zielgruppe bei weiteren Veranstaltungen übernehmen.",
    )

    class Meta:
        model = TargetGroup
        fields = ("name", *CRITERIA_FIELDS)
        localized_fields = ("min_weight", "max_weight")
        widgets = CRITERIA_WIDGETS

    def clean(self) -> dict[str, Any]:
        data = super().clean()
        if data.get("save_as_template") and not data.get("DELETE"):
            name = (data.get("name") or "").strip()
            if not name:
                self.add_error("name", "Für eine Vorlage braucht die Zielgruppe eine Bezeichnung.")
            elif TargetGroupTemplate.objects.filter(name__iexact=name).exists():
                self.add_error("name", f"Eine Vorlage „{name}“ gibt es schon.")
        return data


class BaseTargetGroupFormSet(forms.BaseInlineFormSet):
    def add_fields(self, form: forms.ModelForm, index: int | None) -> None:
        super().add_fields(form, index)
        form.fields["DELETE"].label = "Zielgruppe entfernen"

    def clean(self) -> None:
        super().clean()
        names = [
            (form.cleaned_data.get("name") or "").strip().lower()
            for form in self.forms
            if form.cleaned_data.get("save_as_template") and not form.cleaned_data.get("DELETE")
        ]
        if len(names) != len(set(names)):
            raise forms.ValidationError("Zwei neue Vorlagen haben dieselbe Bezeichnung.")


TargetGroupFormSet = forms.inlineformset_factory(
    Event,
    TargetGroup,
    form=TargetGroupForm,
    formset=BaseTargetGroupFormSet,
    extra=0,
    can_delete=True,
)


class OccurrenceTargetGroupForm(CriteriaForm):
    """Ein Zielgruppen-Block für einen einzelnen Termin (ADR 0019)."""

    class Meta:
        model = OccurrenceTargetGroup
        fields = ("name", *CRITERIA_FIELDS)
        localized_fields = ("min_weight", "max_weight")
        widgets = CRITERIA_WIDGETS


class BaseOccurrenceTargetGroupFormSet(forms.BaseInlineFormSet):
    def add_fields(self, form: forms.ModelForm, index: int | None) -> None:
        super().add_fields(form, index)
        form.fields["DELETE"].label = "Zielgruppe entfernen"


OccurrenceTargetGroupFormSet = forms.inlineformset_factory(
    Occurrence,
    OccurrenceTargetGroup,
    form=OccurrenceTargetGroupForm,
    formset=BaseOccurrenceTargetGroupFormSet,
    extra=0,
    can_delete=True,
)


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = (
            "title",
            "event_type",
            "description",
            "location",
            "capacity",
            "weight_required",
            "guests_welcome",
            "target_mode",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "target_mode": forms.RadioSelect,
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        current = self.instance.event_type_id if self.instance.pk else None
        field = self.fields["event_type"]
        field.queryset = EventType.objects.filter(models.Q(is_active=True) | models.Q(pk=current))  # type: ignore[attr-defined]
        field.empty_label = None  # type: ignore[attr-defined]
        self.fields["target_mode"].required = False  # fehlt der Wert, bleibt es bei der bisherigen Einstellung

    def clean_target_mode(self) -> str:
        return self.cleaned_data.get("target_mode") or self.instance.target_mode or TargetMode.REQUIRED


RHYTHM_FIELDS = ("repeat", "interval", "week_of_month")


def _rhythm_widgets() -> dict[str, forms.Widget]:
    """Rhythmus: Auswahl als Optionen; welches Feld gilt, zeigt ``rhythm.js`` (ohne JavaScript sind beide sichtbar)."""
    return {
        "repeat": forms.RadioSelect(attrs={"data-rhythm": ""}),
        "interval": forms.NumberInput(attrs={"data-rhythm-for": Repeat.WEEKS, "min": 1, "max": 52}),
        "week_of_month": forms.Select(attrs={"data-rhythm-for": Repeat.MONTH}),
    }


def _clean_rhythm(form: forms.BaseForm, data: dict[str, Any]) -> None:
    """Nur das Feld des gewählten Rhythmus zählt; ohne Angabe gilt „alle 1 Woche“."""
    if data.get("repeat") == Repeat.MONTH:
        if data.get("week_of_month") in (None, ""):
            form.add_error("week_of_month", "Wähle bitte, der wievielte im Monat.")
        data["interval"] = 1
    else:
        data["repeat"] = Repeat.WEEKS
        if "interval" not in form.errors:
            data["interval"] = data.get("interval") or 1
        data["week_of_month"] = None


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
    repeat = forms.ChoiceField(
        label="Rhythmus",
        choices=Repeat.choices,
        initial=Repeat.WEEKS,
        required=False,
        widget=_rhythm_widgets()["repeat"],
    )
    interval = forms.IntegerField(
        label=Schedule._meta.get_field("interval").verbose_name,
        help_text=Schedule._meta.get_field("interval").help_text,
        required=False,
        min_value=1,
        max_value=52,
        initial=1,
        widget=_rhythm_widgets()["interval"],
    )
    week_of_month = forms.TypedChoiceField(
        label=Schedule._meta.get_field("week_of_month").verbose_name,
        help_text=Schedule._meta.get_field("week_of_month").help_text,
        choices=[("", "---------"), *WeekOfMonth.choices],
        coerce=int,
        empty_value=None,
        required=False,
        widget=_rhythm_widgets()["week_of_month"],
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
        *RHYTHM_FIELDS,
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
        extra = {"dates", "target_mode", *self.ONCE_FIELDS, *self.WEEKLY_FIELDS, *self.TEAM_FIELDS}
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
            _clean_rhythm(self, data)
        for name in required:
            if not data.get(name) and name not in self.errors:
                self.add_error(name, "Bitte ausfüllen.")
        if bool(data.get("team_member")) != bool(data.get("team_role")):
            self.add_error(
                "team_role", "Für die Übungsleiter bitte Mitglied und Rolle wählen – oder beides leer lassen."
            )
        if mode == self.LATER and data.get("team_member"):
            self.add_error("team_member", "Die Übungsleiter trägst du ein, sobald es Termine gibt.")
        return data


class ScheduleForm(forms.ModelForm):
    class Meta:
        model = Schedule
        fields = (
            "weekday",
            *RHYTHM_FIELDS,
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
            **_rhythm_widgets(),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["repeat"].choices = Repeat.choices  # type: ignore[attr-defined]  # ohne leere Auswahl
        self.fields["interval"].required = False
        self.fields["repeat"].required = False

    def clean(self) -> dict[str, Any]:
        data = super().clean() or {}
        _clean_rhythm(self, data)
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


class HandOverForm(TeamForm):
    """Übertragen (ADR 0018): wer übernimmt, mit welcher Rolle."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["member"].label = "Wer übernimmt?"
        self.fields["role"].label = "Als"


class ConfirmForm(forms.Form):
    minutes = forms.IntegerField(label="Dauer (Minuten)", min_value=1, max_value=24 * 60)


class GuestForm(forms.ModelForm):
    """Daten eines Gastes: vom Team eingetragen, über den Anmeldelink oder auf der Gast-Seite geändert."""

    class Meta:
        model = Guest
        fields = (
            "first_name",
            "last_name",
            "birth_year",
            "gender",
            "grade",
            "weight",
            "club",
            "email",
            "phone",
            "guardian_name",
        )
        localized_fields = ("weight",)
        widgets = {"weight": WeightInput()}

    def __init__(self, *args: Any, event: Event, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.event = event
        if event.weight_required:
            self.fields["weight"].required = True
            self.fields["weight"].help_text = "Für diese Veranstaltung erforderlich."

    def clean(self) -> dict[str, Any]:
        data = super().clean() or {}
        year = data.get("birth_year")
        if year and timezone.localdate().year - year < 18 and not data.get("guardian_name"):
            self.add_error("guardian_name", "Bei Minderjährigen brauchen wir den Namen eines Erziehungsberechtigten.")
        return data


class GuestRegisterForm(GuestForm):
    """Öffentliche Anmeldung über den Link der Veranstaltung (ohne Zugang)."""

    occurrences = forms.ModelMultipleChoiceField(
        label="Termine", queryset=Occurrence.objects.none(), widget=forms.CheckboxSelectMultiple
    )
    consent = forms.BooleanField(
        label="Ich habe den Datenschutzhinweis gelesen und bin einverstanden, dass meine Angaben für diese "
        "Veranstaltung gespeichert werden.",
    )
    # Honeypot gegen Spam: Menschen sehen das Feld nicht und lassen es leer.
    website = forms.CharField(label="Webseite", required=False)

    def __init__(self, *args: Any, event: Event, occurrences: list[Occurrence], **kwargs: Any) -> None:
        super().__init__(*args, event=event, **kwargs)
        field = self.fields["occurrences"]
        field.queryset = Occurrence.objects.filter(pk__in=[o.pk for o in occurrences])  # type: ignore[attr-defined]
        field.label_from_instance = lambda o: (  # type: ignore[attr-defined]
            f"{formats.date_format(timezone.localtime(o.starts_at), 'D d.m.Y, H:i')}–"
            f"{timezone.localtime(o.ends_at):%H:%M} Uhr"
        )
        if len(occurrences) == 1:
            field.initial = [occurrences[0].pk]

    def clean_website(self) -> str:
        if self.cleaned_data.get("website"):
            raise forms.ValidationError("Bitte lass dieses Feld leer.")
        return ""


class AgendaFilterForm(forms.Form):
    """Filter der Seite „Termine“. Das versteckte Feld „f“ markiert ein abgeschicktes Formular; ohne gelten die
    Standardwerte (für eigene Mitglieder: nur passende Termine)."""

    passend = forms.BooleanField(label="Nur passende Termine", required=False, initial=True)
    mitglied = forms.TypedChoiceField(label="Mitglied", required=False, coerce=int, empty_value=None)
    art = forms.ModelChoiceField(label="Art", queryset=EventType.objects.all(), required=False, empty_label="alle")
    veranstaltung = forms.ModelChoiceField(
        label="Veranstaltung", queryset=Event.objects.order_by("title"), required=False, empty_label="alle"
    )
    von = forms.DateField(label="Von", required=False, widget=DateInput())
    bis = forms.DateField(label="Bis", required=False, widget=DateInput())
    meine = forms.BooleanField(label="Nur meine Anmeldungen", required=False)
    offen = forms.BooleanField(label="Nur mit offener Anmeldung", required=False)
    ohne_abgesagte = forms.BooleanField(label="Abgesagte ausblenden", required=False)

    def __init__(self, data: Any, *, links: list[Any]) -> None:
        super().__init__(data if data is not None and "f" in data else None)
        self.has_members = bool(links)
        if len(links) > 1:
            field = cast(forms.TypedChoiceField, self.fields["mitglied"])
            field.choices = [("", "alle"), *((link.member.pk, link.member.first_name) for link in links)]
        else:
            del self.fields["mitglied"]
        if not links:
            del self.fields["passend"], self.fields["meine"]

    def clean(self) -> dict[str, Any]:
        data = super().clean() or {}
        if data.get("von") and data.get("bis") and data["bis"] < data["von"]:
            self.add_error("bis", "„Bis“ muss nach „Von“ liegen.")
        return data

    def to_filter(self) -> AgendaFilter:
        if not self.is_bound or not self.is_valid():
            return AgendaFilter(matching=self.has_members)
        data = self.cleaned_data
        return AgendaFilter(
            matching=bool(data.get("passend")),
            member=data.get("mitglied"),
            event_type=data["art"].pk if data.get("art") else None,
            event=data["veranstaltung"].pk if data.get("veranstaltung") else None,
            start=data.get("von"),
            end=data.get("bis"),
            mine=bool(data.get("meine")),
            open=bool(data.get("offen")),
            hide_cancelled=bool(data.get("ohne_abgesagte")),
        )

    @property
    def changed_count(self) -> int:
        """Wie viele Filter vom Standard abweichen (für die Zusammenfassung)."""
        if not self.is_bound or not self.is_valid():
            return 0
        default = {"passend": self.has_members}
        return sum(1 for name in self.fields if bool(self.cleaned_data.get(name)) != default.get(name, False))
