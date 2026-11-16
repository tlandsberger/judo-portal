from __future__ import annotations

import json
from typing import Any

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from portal.accounts.models import User
from portal.core import audit
from portal.members.models import Member

from . import pdf, services
from .forms import AuditFilterForm, DeleteForm


def _manager(request: HttpRequest) -> None:
    if not services.can_manage(request.user):
        raise PermissionDenied


def _download(data: dict[str, Any], name: str, subject: str, as_json: bool) -> HttpResponse:
    """Datenauskunft als PDF; maschinenlesbar (Art. 20) als JSON mit ``?format=json``."""
    stamp = f"{timezone.localdate():%Y-%m-%d}"
    if as_json:
        response = HttpResponse(
            json.dumps(data, ensure_ascii=False, indent=2), content_type="application/json; charset=utf-8"
        )
        response["Content-Disposition"] = f'attachment; filename="{name}-{stamp}.json"'
    else:
        response = HttpResponse(pdf.render(data, subject), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{name}-{stamp}.pdf"'
    response["Cache-Control"] = "no-store"
    return response


@login_required
def my_privacy(request: HttpRequest) -> HttpResponse:
    """Datenauskunft zum eigenen Benutzer und zu den eigenen Mitgliedern (Art. 15)."""
    user: User = request.user  # type: ignore[assignment]
    data = services.export(user)
    if request.GET.get("format") in ("pdf", "json"):
        return _download(data, "datenauskunft", user.display_name, request.GET["format"] == "json")
    response = render(request, "privacy/my_privacy.html", {"data": data})
    response["Cache-Control"] = "no-store"
    return response


@login_required
def member_export(request: HttpRequest, pk: int) -> HttpResponse:
    _manager(request)
    member = get_object_or_404(Member, pk=pk)
    name = f"datenauskunft-{member.member_number or member.pk}"
    return _download(services.export_member(member), name, member.display_name, request.GET.get("format") == "json")


@login_required
def member_delete(request: HttpRequest, pk: int) -> HttpResponse:
    _manager(request)
    member = get_object_or_404(Member, pk=pk)
    preview = services.preview_deletion(member)
    form = DeleteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        name = member.display_name
        services.delete_member(member, request.user, services.REASON_REQUEST)  # type: ignore[arg-type]
        messages.success(request, f"{name} ist gelöscht.")
        return redirect("member_list")
    return render(
        request,
        "privacy/member_delete.html",
        {"member": member, "preview": preview, "form": form, "when": services.deletion_date(member)},
    )


@login_required
def own_access_delete(request: HttpRequest) -> HttpResponse:
    """Eigenen Zugang löschen, mit Bestätigung. Die verknüpften Mitglieder bleiben erhalten."""
    user: User = request.user  # type: ignore[assignment]
    blocked = None
    try:
        services.check_own_deletion(user)
    except services.DeletionError as error:
        blocked = str(error)
    form = DeleteForm(request.POST or None)
    if request.method == "POST" and not blocked and form.is_valid():
        logout(request)
        services.delete_own_access(user)
        messages.success(request, "Dein Zugang ist gelöscht. Wir haben dir eine Bestätigung per Mail geschickt.")
        return redirect("account_login")
    links = user.member_links.select_related("member")
    return render(request, "privacy/own_access_delete.html", {"form": form, "links": links, "blocked": blocked})


@login_required
def audit_list(request: HttpRequest) -> HttpResponse:
    _manager(request)
    form = AuditFilterForm(request.GET or None)
    rows = audit.entries()
    if form.is_valid():
        data = form.cleaned_data
        rows = audit.entries(area=data["area"] or None, since=data["since"], until=data["until"])
        if data["q"]:
            rows = rows.filter(summary__icontains=data["q"]) | rows.filter(actor_name__icontains=data["q"])
    member_id = request.GET.get("mitglied")
    if member_id and member_id.isdigit():
        rows = rows.filter(member_id=int(member_id))
    page = Paginator(rows.order_by("-at", "-pk"), 50).get_page(request.GET.get("seite"))
    query = request.GET.copy()
    query.pop("seite", None)
    return render(
        request,
        "privacy/audit_list.html",
        {"form": form, "page": page, "query": query.urlencode(), "keep_days": audit.KEEP_DAYS},
    )
