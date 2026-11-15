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
from .forms import InvitationForm, PhoneForm, RolesForm
from .models import Invitation, Role, User
from .permissions import MANAGE_USERS, role_required


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
    """„Meine Anmeldung“: Passkeys, Passwort, angemeldete Geräte und Telefon für Notfälle."""
    form = PhoneForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Telefon gespeichert.")
        return redirect("security")
    context = _login_methods(request.user)  # type: ignore[arg-type]
    context["phone_form"] = form
    return render(request, "accounts/security.html", context)


def _login_methods(user: User) -> dict[str, object]:
    passkeys = Authenticator.objects.filter(user=user, type=Authenticator.Type.WEBAUTHN)
    return {"passkeys": passkeys, "has_password": user.has_usable_password()}


@role_required(*MANAGE_USERS)
def user_list(request: HttpRequest) -> HttpResponse:
    users = [(target_user, services.is_set_up(target_user)) for target_user in User.objects.all()]
    invitations = Invitation.objects.filter(accepted_at__isnull=True)
    return render(
        request,
        "accounts/user_list.html",
        {"users": users, "invitations": invitations, "roles": Role},
    )


@role_required(*MANAGE_USERS)
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
        return redirect("user_list")
    return render(request, "accounts/invite.html", {"form": form})


@require_POST
@role_required(*MANAGE_USERS)
def resend_invitation(request: HttpRequest, pk: int) -> HttpResponse:
    invitation = get_object_or_404(Invitation, pk=pk, accepted_at__isnull=True)
    services.resend(invitation)
    messages.success(request, f"Einladung an {invitation.email} erneut verschickt.")
    return redirect("user_list")


@require_POST
@role_required(*MANAGE_USERS)
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
@role_required(*MANAGE_USERS)
def reinvite_user(request: HttpRequest, pk: int) -> HttpResponse:
    """Neue Einladung für einen Benutzer, der seinen Zugang noch nicht eingerichtet hat (per Mail oder nur Link)."""
    target_user = get_object_or_404(User, pk=pk, is_active=True)
    if services.has_login_method(target_user):
        messages.info(request, f"{target_user.display_name} hat den Zugang bereits eingerichtet.")
        return redirect("user_list")
    link_only = request.POST.get("action") == "link"
    invitation = services.reinvite(target_user, invited_by=request.user, send=not link_only)  # type: ignore[arg-type]
    if link_only:
        return _show_link(request, invitation)
    messages.success(request, f"Einladung an {target_user.email} erneut verschickt.")
    return redirect("user_list")


@require_POST
@role_required(*MANAGE_USERS)
def delete_invitation(request: HttpRequest, pk: int) -> HttpResponse:
    invitation = get_object_or_404(Invitation, pk=pk, accepted_at__isnull=True)
    invitation.delete()
    messages.success(request, f"Einladung an {invitation.email} zurückgezogen.")
    return redirect("user_list")


@role_required(*MANAGE_USERS)
def edit_user(request: HttpRequest, pk: int) -> HttpResponse:
    target_user = get_object_or_404(User, pk=pk)
    actor: User = request.user  # type: ignore[assignment]
    allow_admin = actor.has_role(Role.ADMIN)
    # Administratoren darf nur ein Administrator ändern.
    if target_user.has_role(Role.ADMIN) and not allow_admin:
        messages.error(request, "Administratoren kann nur ein Administrator ändern.")
        return redirect("user_list")
    form = RolesForm(request.POST or None, allow_admin=allow_admin, initial={"roles": target_user.roles})
    if request.method == "POST" and form.is_valid():
        roles = list(form.cleaned_data["roles"])
        if not allow_admin and Role.ADMIN in target_user.roles:
            roles.append(Role.ADMIN)
        if target_user == actor and Role.ADMIN in target_user.roles and Role.ADMIN not in roles:
            messages.error(request, "Du kannst dir die Administrator-Rolle nicht selbst entziehen.")
            return redirect("edit_user", pk=target_user.pk)
        target_user.set_roles(roles)
        messages.success(request, f"Rollen von {target_user.display_name} gespeichert.")
        return redirect("user_list")
    return render(request, "accounts/edit_user.html", {"target_user": target_user, "form": form})


@require_POST
@role_required(*MANAGE_USERS)
def toggle_active(request: HttpRequest, pk: int) -> HttpResponse:
    target_user = get_object_or_404(User, pk=pk)
    actor: User = request.user  # type: ignore[assignment]
    if target_user == actor:
        messages.error(request, "Du kannst dich nicht selbst deaktivieren.")
    elif target_user.has_role(Role.ADMIN) and not actor.has_role(Role.ADMIN):
        messages.error(request, "Administratoren kann nur ein Administrator ändern.")
    else:
        target_user.is_active = not target_user.is_active
        # Deaktivierte Benutzer gelten sofort als abgemeldet: Django lässt inaktive Nutzer nicht mehr durch.
        target_user.save(update_fields=["is_active"])
        state = "aktiviert" if target_user.is_active else "deaktiviert"
        messages.success(request, f"{target_user.display_name} {state}.")
    return redirect("user_list")
