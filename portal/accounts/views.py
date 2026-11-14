from __future__ import annotations

from allauth.mfa.models import Authenticator
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import services
from .forms import InvitationForm, RolesForm
from .models import Invitation, Role, User
from .permissions import MANAGE_ACCOUNTS, role_required


def accept_invitation(request: HttpRequest, token: str) -> HttpResponse:
    """Einladungslink. Angenommen wird erst per Klick (POST), damit Link-Vorschauen in Mailprogrammen
    die Einladung nicht verbrauchen."""
    invitation = Invitation.objects.filter(token=token).first()
    if invitation is None or not invitation.is_valid:
        return render(request, "accounts/invitation_invalid.html", status=410)
    if request.method == "POST":
        services.accept(invitation, request)
        return redirect("setup_login")
    return render(request, "accounts/invitation_accept.html", {"invitation": invitation})


@login_required
def setup_login(request: HttpRequest) -> HttpResponse:
    """Nach der Einladung: Anmeldewege einrichten (Passkey, Passwort oder nur Mail-Code)."""
    return render(request, "accounts/setup_login.html", _login_methods(request.user))  # type: ignore[arg-type]


@login_required
def security(request: HttpRequest) -> HttpResponse:
    """„Meine Anmeldung“: Passkeys, Passwort, angemeldete Geräte."""
    return render(request, "accounts/security.html", _login_methods(request.user))  # type: ignore[arg-type]


def _login_methods(user: User) -> dict[str, object]:
    passkeys = Authenticator.objects.filter(user=user, type=Authenticator.Type.WEBAUTHN)
    return {"passkeys": passkeys, "has_password": user.has_usable_password()}


@role_required(*MANAGE_ACCOUNTS)
def account_list(request: HttpRequest) -> HttpResponse:
    users = User.objects.all()
    invitations = Invitation.objects.filter(accepted_at__isnull=True)
    return render(
        request,
        "accounts/account_list.html",
        {"users": users, "invitations": invitations, "roles": Role},
    )


@role_required(*MANAGE_ACCOUNTS)
def invite(request: HttpRequest) -> HttpResponse:
    allow_admin = request.user.has_role(Role.ADMIN)  # type: ignore[union-attr]
    form = InvitationForm(request.POST or None, allow_admin=allow_admin)
    if request.method == "POST" and form.is_valid():
        invitation = services.invite(
            form.cleaned_data["email"],
            first_name=form.cleaned_data["first_name"],
            last_name=form.cleaned_data["last_name"],
            roles=form.cleaned_data["roles"],
            invited_by=request.user,  # type: ignore[arg-type]
        )
        messages.success(request, f"Einladung an {invitation.email} verschickt.")
        return redirect("account_list")
    return render(request, "accounts/invite.html", {"form": form})


@require_POST
@role_required(*MANAGE_ACCOUNTS)
def resend_invitation(request: HttpRequest, pk: int) -> HttpResponse:
    invitation = get_object_or_404(Invitation, pk=pk, accepted_at__isnull=True)
    services.resend(invitation)
    messages.success(request, f"Einladung an {invitation.email} erneut verschickt.")
    return redirect("account_list")


@require_POST
@role_required(*MANAGE_ACCOUNTS)
def delete_invitation(request: HttpRequest, pk: int) -> HttpResponse:
    invitation = get_object_or_404(Invitation, pk=pk, accepted_at__isnull=True)
    invitation.delete()
    messages.success(request, f"Einladung an {invitation.email} zurückgezogen.")
    return redirect("account_list")


@role_required(*MANAGE_ACCOUNTS)
def edit_account(request: HttpRequest, pk: int) -> HttpResponse:
    account = get_object_or_404(User, pk=pk)
    actor: User = request.user  # type: ignore[assignment]
    allow_admin = actor.has_role(Role.ADMIN)
    # Administratoren-Konten darf nur ein Administrator ändern.
    if account.has_role(Role.ADMIN) and not allow_admin:
        messages.error(request, "Administratoren kann nur ein Administrator ändern.")
        return redirect("account_list")
    form = RolesForm(request.POST or None, allow_admin=allow_admin, initial={"roles": account.roles})
    if request.method == "POST" and form.is_valid():
        roles = list(form.cleaned_data["roles"])
        if not allow_admin and Role.ADMIN in account.roles:
            roles.append(Role.ADMIN)
        if account == actor and Role.ADMIN in account.roles and Role.ADMIN not in roles:
            messages.error(request, "Du kannst dir die Administrator-Rolle nicht selbst entziehen.")
            return redirect("edit_account", pk=account.pk)
        account.set_roles(roles)
        messages.success(request, f"Rollen von {account.display_name} gespeichert.")
        return redirect("account_list")
    return render(request, "accounts/edit_account.html", {"account": account, "form": form})


@require_POST
@role_required(*MANAGE_ACCOUNTS)
def toggle_active(request: HttpRequest, pk: int) -> HttpResponse:
    account = get_object_or_404(User, pk=pk)
    actor: User = request.user  # type: ignore[assignment]
    if account == actor:
        messages.error(request, "Du kannst dein eigenes Konto nicht deaktivieren.")
    elif account.has_role(Role.ADMIN) and not actor.has_role(Role.ADMIN):
        messages.error(request, "Administratoren kann nur ein Administrator ändern.")
    else:
        account.is_active = not account.is_active
        # Deaktivierte Konten gelten sofort als abgemeldet: Django lässt inaktive Nutzer nicht mehr durch.
        account.save(update_fields=["is_active"])
        state = "aktiviert" if account.is_active else "deaktiviert"
        messages.success(request, f"Konto von {account.display_name} {state}.")
    return redirect("account_list")
