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
    layout = (("first_name", "last_name"),)

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

    layout = (("first_name", "last_name"),)

    class Meta:
        model = User
        fields = ("first_name", "last_name")

    def __init__(self, *args: Any, allow_admin: bool, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["roles"] = RolesField(allow_admin=allow_admin, initial=self.instance.roles)


class ProfileForm(forms.ModelForm):
    """„Meine Daten“: Name und Telefon, die jeder Benutzer selbst pflegt."""

    layout = (("first_name", "last_name"),)

    class Meta:
        model = User
        fields = ("first_name", "last_name", "phone")
        widgets = {
            "first_name": forms.TextInput(attrs={"autocomplete": "given-name"}),
            "last_name": forms.TextInput(attrs={"autocomplete": "family-name"}),
            "phone": forms.TextInput(attrs={"type": "tel", "autocomplete": "tel"}),
        }


class EmailChangeForm(forms.Form):
    """Neue E-Mail-Adresse; gilt erst nach Bestätigung über den Link an die neue Adresse (ADR 0011)."""

    email = forms.EmailField(label="Neue E-Mail-Adresse")
    sync_member = forms.BooleanField(required=False, initial=True)

    def __init__(self, *args: Any, member_name: str = "", own: bool = True, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if member_name:
            whose = "meine Mitgliedsdaten" if own else f"die Mitgliedsdaten von {member_name}"
            self.fields["sync_member"].label = f"Auch in {whose} übernehmen"
            self.fields["sync_member"].help_text = "Sobald die neue Adresse bestätigt ist."
        else:
            del self.fields["sync_member"]

    def clean_email(self) -> str:
        email: str = self.cleaned_data["email"].strip().lower()
        return email
