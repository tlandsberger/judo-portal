from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from portal.accounts import services as accounts
from portal.accounts.permissions import role_required

from . import csv_import, services
from .forms import AccessForm, ImportForm, InterestForm, MemberForm, SelfServiceForm
from .models import Interest, Member, MemberLink
from .services import MANAGE_MEMBERS

IMPORT_SESSION_KEY = "members_import_csv"


# Mitgliederliste und Detailseite (Abteilungsleitung)


@role_required(*MANAGE_MEMBERS)
def member_list(request: HttpRequest) -> HttpResponse:
    members = Member.objects.all()
    query = request.GET.get("q", "").strip()
    show_former = request.GET.get("ehemalige") == "1"
    if query:
        members = members.filter(
            Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(member_number__icontains=query)
        )
    member_rows = [member for member in members if show_former or member.is_active]
    return render(
        request,
        "members/member_list.html",
        {
            "members": member_rows,
            "query": query,
            "show_former": show_former,
        },
    )


@role_required(*MANAGE_MEMBERS)
def member_detail(request: HttpRequest, pk: int) -> HttpResponse:
    member = get_object_or_404(Member, pk=pk)
    kinds = services.link_kinds_for(member)
    context = {
        "member": member,
        "links": member.links.select_related("user"),
        "pending": member.pending_links.filter(invitation__accepted_at__isnull=True).select_related("invitation"),
        "access_form": AccessForm(kinds=kinds, member=member) if kinds else None,
    }
    return render(request, "members/member_detail.html", context)


@role_required(*MANAGE_MEMBERS)
def member_edit(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    member = get_object_or_404(Member, pk=pk) if pk else None
    form = MemberForm(request.POST or None, instance=member)
    if request.method == "POST" and form.is_valid():
        member = form.save()
        messages.success(request, f"{member.display_name} gespeichert.")
        return redirect("member_detail", pk=member.pk)
    return render(request, "members/member_edit.html", {"form": form, "member": member})


@require_POST
@role_required(*MANAGE_MEMBERS)
def member_access(request: HttpRequest, pk: int) -> HttpResponse:
    """Zugang für das Mitglied selbst oder einen Elternteil: Einladung oder direkte Verknüpfung."""
    member = get_object_or_404(Member, pk=pk)
    form = AccessForm(request.POST, kinds=services.link_kinds_for(member), member=member)
    if not form.is_valid():
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, str(error))
        return redirect("member_detail", pk=member.pk)
    link_only = request.POST.get("action") == "link"
    try:
        _, invitation = services.give_access(
            member,
            form.cleaned_data["email"],
            form.cleaned_data["kind"],
            invited_by=request.user,  # type: ignore[arg-type]
            send=not link_only,
        )
    except ValueError as error:
        messages.error(request, str(error))
        return redirect("member_detail", pk=member.pk)
    if invitation is None:
        messages.success(request, f"Mit dem Benutzer {form.cleaned_data['email']} verknüpft und benachrichtigt.")
    elif link_only:
        response = render(
            request,
            "accounts/invitation_link.html",
            {"invitation": invitation, "url": accounts.invitation_url(invitation)},
        )
        response["Cache-Control"] = "no-store"
        return response
    else:
        messages.success(request, f"Einladung an {invitation.email} verschickt.")
    return redirect("member_detail", pk=member.pk)


@require_POST
@role_required(*MANAGE_MEMBERS)
def member_unlink(request: HttpRequest, pk: int, link_pk: int) -> HttpResponse:
    member_link = get_object_or_404(MemberLink, pk=link_pk, member_id=pk)
    services.unlink(member_link)
    messages.success(request, f"Verknüpfung mit {member_link.user.display_name} gelöst.")
    return redirect("member_detail", pk=pk)


# Interessen (Liste für Mitglieder und Zielgruppen)


@role_required(*MANAGE_MEMBERS)
def interest_list(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    interest = get_object_or_404(Interest, pk=pk) if pk else None
    form = InterestForm(request.POST or None, instance=interest)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        messages.success(request, f"Interesse „{saved.name}“ gespeichert.")
        return redirect("interest_list")
    return render(
        request,
        "members/interest_list.html",
        {"interests": Interest.objects.all(), "form": form, "interest": interest},
    )


@require_POST
@role_required(*MANAGE_MEMBERS)
def interest_delete(request: HttpRequest, pk: int) -> HttpResponse:
    interest = get_object_or_404(Interest, pk=pk)
    interest.delete()
    messages.success(request, f"Interesse „{interest.name}“ gelöscht.")
    return redirect("interest_list")


# CSV-Import


@role_required(*MANAGE_MEMBERS)
def member_import(request: HttpRequest) -> HttpResponse:
    """Schritt 1: Datei hochladen, Vorschau zeigen. Schritt 2 (``action=apply``): übernehmen."""
    form = ImportForm()
    if request.method == "POST" and request.POST.get("action") == "apply":
        text = request.session.pop(IMPORT_SESSION_KEY, None)
        if not text:
            messages.error(request, "Die Vorschau ist abgelaufen. Lade die Datei bitte noch einmal hoch.")
            return redirect("member_import")
        result = csv_import.apply(text)
        counts = result.counts
        messages.success(
            request,
            f"Import abgeschlossen: {counts['new']} neu, {counts['changed']} aktualisiert"
            + (f", {counts['error']} Zeilen mit Fehlern übersprungen." if counts["error"] else "."),
        )
        return redirect("member_list")
    if request.method == "POST":
        form = ImportForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                text = csv_import.decode(form.cleaned_data["file"].read())
                preview = csv_import.preview(text)
            except csv_import.CsvError as error:
                form.add_error("file", str(error))
            else:
                request.session[IMPORT_SESSION_KEY] = text
                return render(request, "members/import_preview.html", {"preview": preview})
    return render(request, "members/import.html", {"form": form})


@role_required(*MANAGE_MEMBERS)
def import_template(request: HttpRequest) -> HttpResponse:
    response = HttpResponse(csv_import.template_csv(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="mitglieder-vorlage.csv"'
    return response


# Meine Daten (Mitglieder und Eltern)


@login_required
def my_data(request: HttpRequest) -> HttpResponse:
    """Ein verknüpftes Mitglied: direkt dessen Seite. Mehrere: Übersicht mit einer Karte je Mitglied."""
    links = services.effective_links(request.user)
    if len(links) == 1:
        return redirect("my_member", pk=links[0].member.pk)
    return render(request, "members/my_data.html", {"links": links})


@login_required
def my_member(request: HttpRequest, pk: int) -> HttpResponse:
    member = _own_member(request, pk)
    several = len(services.effective_links(request.user)) > 1
    return render(request, "members/my_member.html", {"member": member, "several": several})


@login_required
def my_member_edit(request: HttpRequest, pk: int) -> HttpResponse:
    member = _own_member(request, pk)
    form = SelfServiceForm(request.POST or None, instance=member)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Deine Änderungen sind gespeichert.")
        return redirect("my_member", pk=member.pk)
    return render(request, "members/my_member_edit.html", {"member": member, "form": form})


def _own_member(request: HttpRequest, pk: int) -> Member:
    member = get_object_or_404(Member, pk=pk)
    if not services.can_self_edit(request.user, member):
        raise PermissionDenied
    return member
