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
            help_text="Eltern und Mitglieder brauchen keine Rolle; die Verknüpfung mit Mitgliedern kommt später.",
        )

    def clean_email(self) -> str:
        email: str = self.cleaned_data["email"].strip().lower()
        user = User.objects.filter(email=email).first()
        if user and user.is_active:
            raise forms.ValidationError("Zu dieser Adresse gibt es bereits einen aktiven Benutzer.")
        return email


class RolesForm(forms.Form):
    def __init__(self, *args: Any, allow_admin: bool, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["roles"] = RolesField(allow_admin=allow_admin)
