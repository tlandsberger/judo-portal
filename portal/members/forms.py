from __future__ import annotations

from typing import Any

from django import forms

from .models import Interest, LinkKind, Member


class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(format="%Y-%m-%d", **kwargs)


class WeightInput(forms.TextInput):
    """Gewicht mit Komma (deutsche Tastatur am Handy); Django liest „65,5“ über localize."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(attrs={"inputmode": "decimal", "autocomplete": "off"}, **kwargs)


class MemberForm(forms.ModelForm):
    """Alle Daten eines Mitglieds (Abteilungsleitung)."""

    layout = (
        ("first_name", "last_name"),
        ("birth_date", "gender"),
        ("joined_on", "left_on"),
        ("email", "phone"),
        ("grade", "weight"),
    )

    class Meta:
        model = Member
        fields = (
            "first_name",
            "last_name",
            "birth_date",
            "gender",
            "member_number",
            "joined_on",
            "left_on",
            "email",
            "phone",
            "grade",
            "weight",
            "interests",
        )
        localized_fields = ("weight",)
        widgets = {
            "interests": forms.CheckboxSelectMultiple(),
            "birth_date": DateInput(),
            "joined_on": DateInput(),
            "left_on": DateInput(),
            "weight": WeightInput(),
            "phone": forms.TextInput(attrs={"type": "tel", "autocomplete": "off"}),
        }

    def clean_member_number(self) -> str | None:
        return (self.cleaned_data.get("member_number") or "").strip() or None


class SelfServiceForm(forms.ModelForm):
    """Was Mitglieder und Eltern selbst pflegen: Kontakt- und Judo-Daten."""

    layout = (("email", "phone"), ("grade", "weight"))

    class Meta:
        model = Member
        fields = ("email", "phone", "grade", "weight", "interests")
        localized_fields = ("weight",)
        widgets = {
            "weight": WeightInput(),
            "phone": forms.TextInput(attrs={"type": "tel", "autocomplete": "tel"}),
            "interests": forms.CheckboxSelectMultiple(),
        }
        help_texts = {"interests": "Danach zeigt dir das Portal passende Veranstaltungen."}


class AccessForm(forms.Form):
    """Zugang für ein Mitglied: das Mitglied selbst (ab 14) oder ein Elternteil (bis 18)."""

    kind = forms.ChoiceField(label="Für", widget=forms.RadioSelect)
    email = forms.EmailField(label="E-Mail")

    def __init__(self, *args: Any, kinds: list[LinkKind], member: Member, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        labels = {LinkKind.SELF: f"{member.first_name} selbst", LinkKind.GUARDIAN: "Elternteil"}
        choices = [(kind.value, labels[kind]) for kind in kinds]
        self.fields["kind"].choices = choices  # type: ignore[attr-defined]
        if kinds:
            self.fields["kind"].initial = kinds[0].value
        if member.email and LinkKind.SELF in kinds:
            self.fields["email"].initial = member.email

    def clean_email(self) -> str:
        return str(self.cleaned_data["email"]).strip().lower()


class ImportForm(forms.Form):
    file = forms.FileField(
        label="CSV-Datei", help_text="Spalten wie in der Vorlage, getrennt mit Semikolon oder Komma."
    )


class InterestForm(forms.ModelForm):
    class Meta:
        model = Interest
        fields = ("name",)
