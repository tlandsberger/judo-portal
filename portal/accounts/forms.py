from __future__ import annotations

from typing import Any

from django import forms

from .models import Role, User


class RolesField(forms.MultipleChoiceField):
    widget = forms.CheckboxSelectMultiple

    def __init__(self, *, allow_admin: bool, **kwargs: Any) -> None:
        choices = [c for c in Role.choices if allow_admin or c[0] != Role.ADMIN]
        super().__init__(choices=choices, required=False, label="Rollen", **kwargs)


class InvitationForm(forms.Form):
    email = forms.EmailField(label="E-Mail")
    first_name = forms.CharField(label="Vorname", max_length=100, required=False)
    last_name = forms.CharField(label="Nachname", max_length=100, required=False)

    def __init__(self, *args: Any, allow_admin: bool, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["roles"] = RolesField(
            allow_admin=allow_admin,
            help_text=(
                "Eltern und Mitglieder brauchen keine Rolle. Lade sie am besten über ihr Mitglied ein "
                "(Mitglieder → Zugang geben), dann sind sie gleich verknüpft."
            ),
        )

    def clean_email(self) -> str:
        email: str = self.cleaned_data["email"].strip().lower()
        user = User.objects.filter(email=email).first()
        if user and user.is_active:
            raise forms.ValidationError("Zu dieser Adresse gibt es bereits einen aktiven Benutzer.")
        return email


class UserForm(forms.ModelForm):
    """Name und Rollen eines Benutzers (Benutzerverwaltung)."""

    class Meta:
        model = User
        fields = ("first_name", "last_name")

    def __init__(self, *args: Any, allow_admin: bool, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["roles"] = RolesField(allow_admin=allow_admin, initial=self.instance.roles)


class ProfileForm(forms.ModelForm):
    """„Meine Daten“: Name und Telefon, die jeder Benutzer selbst pflegt."""

    class Meta:
        model = User
        fields = ("first_name", "last_name", "phone")
        widgets = {
            "first_name": forms.TextInput(attrs={"autocomplete": "given-name"}),
            "last_name": forms.TextInput(attrs={"autocomplete": "family-name"}),
            "phone": forms.TextInput(attrs={"type": "tel", "autocomplete": "tel"}),
        }
