from __future__ import annotations

from allauth.mfa.models import Authenticator
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from . import services
from .forms import InvitationForm, RolesForm
from .models import Invitation, Role, User
from .permissions import MANAGE_ACCOUNTS, role_required


@never_cache
def accept_invitation(request: HttpRequest, token: str) -> HttpResponse:
    """Einladungslink. Angenommen wird per Klick (POST); auch dann gibt es nur eine Einrichtungs-Sitzung
    (``services.accept``), damit Mail-Scanner, die Links öffnen und Buttons klicken, keinen Zugang bekommen."""
    invitation = Invitation.objects.filter(token=token).first()
    state = services.invitation_state(invitation)
    if state != "open":
        response = _no_body_for_head(
            request, render(request, "accounts/invitation_invalid.html", {"state": state}, status=410)
        )
    elif request.method == "POST" and invitation is not None:
        if services.accept(invitation, request) is None:
            response = render(request, "accounts/invitation_invalid.html", {"state": "done"})
        else:
            response = redirect("setup_login")
    else:
        response = _no_body_for_head(
            request, render(request, "accounts/invitation_accept.html", {"invitation": invitation})
        )
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


def _no_body_for_head(request: HttpRequest, response: HttpResponse) -> HttpResponse:
    if request.method == "HEAD":
        return HttpResponse(status=response.status_code)
    return response


@require_POST
@login_required
def setup_login_by_code(request: HttpRequest) -> HttpResponse:
    """„Lieber per Code anmelden“: Einrichtungs-Sitzung beenden, voller Zugang erst mit dem Mail-Code."""
    email = request.user.email  # type: ignore[union-attr]
    logout(request)
    messages.info(request, f"Lass dir jetzt einen Anmeldecode an {email} schicken.")
    return redirect("account_request_login_code")


@login_required
def setup_login(request: HttpRequest) -> HttpResponse:
    """Nach der Einladung: Anmeldewege einrichten (Passkey, Passwort oder nur Mail-Code)."""
    context = _login_methods(request.user)  # type: ignore[arg-type]
    context["setup_pending"] = bool(request.session.get(services.SETUP_SESSION_KEY))
    return render(request, "accounts/setup_login.html", context)


@login_required
def security(request: HttpRequest) -> HttpResponse:
    """„Meine Anmeldung“: Passkeys, Passwort, angemeldete Geräte."""
    return render(request, "accounts/security.html", _login_methods(request.user))  # type: ignore[arg-type]


def _login_methods(user: User) -> dict[str, object]:
    passkeys = Authenticator.objects.filter(user=user, type=Authenticator.Type.WEBAUTHN)
    return {"passkeys": passkeys, "has_password": user.has_usable_password()}


@role_required(*MANAGE_ACCOUNTS)
def account_list(request: HttpRequest) -> HttpResponse:
    users = [(account, services.is_set_up(account)) for account in User.objects.all()]
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
        link_only = request.POST.get("action") == "link"
        invitation = services.invite(
            form.cleaned_data["email"],
            first_name=form.cleaned_data["first_name"],
            last_name=form.cleaned_data["last_name"],
            roles=form.cleaned_data["roles"],
            invited_by=request.user,  # type: ignore[arg-type]
            send=not link_only,
        )
        if link_only:
            return _show_link(request, invitation)
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
def invitation_link(request: HttpRequest, pk: int) -> HttpResponse:
    """Neuen Einladungslink erzeugen und anzeigen (zum Kopieren), ohne Mail."""
    invitation = get_object_or_404(Invitation, pk=pk, accepted_at__isnull=True)
    services.new_link(invitation)
    return _show_link(request, invitation)


def _show_link(request: HttpRequest, invitation: Invitation) -> HttpResponse:
    response = render(
        request,
        "accounts/invitation_link.html",
        {"invitation": invitation, "url": services.invitation_url(invitation)},
    )
    response["Cache-Control"] = "no-store"
    return response


@require_POST
@role_required(*MANAGE_ACCOUNTS)
def reinvite_account(request: HttpRequest, pk: int) -> HttpResponse:
    """Neue Einladung für ein Konto, das seinen Zugang noch nicht eingerichtet hat (per Mail oder nur Link)."""
    account = get_object_or_404(User, pk=pk, is_active=True)
    if services.has_login_method(account):
        messages.info(request, f"{account.display_name} hat den Zugang bereits eingerichtet.")
        return redirect("account_list")
    link_only = request.POST.get("action") == "link"
    invitation = services.reinvite(account, invited_by=request.user, send=not link_only)  # type: ignore[arg-type]
    if link_only:
        return _show_link(request, invitation)
    messages.success(request, f"Einladung an {account.email} erneut verschickt.")
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
