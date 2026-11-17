from __future__ import annotations

import csv
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import formats, timezone
from django.views.decorators.http import require_POST

from portal.accounts.models import User
from portal.core import audit
from portal.events import services as events
from portal.members.models import Member

from . import pdf, services
from .forms import ClaimFilterForm, RateForm, SendBackForm
from .models import Claim, ClaimStatus, Rate
from .services import BillingError


def _user(request: HttpRequest) -> User:
    return request.user  # type: ignore[return-value]


def _own_member(request: HttpRequest) -> Member:
    member = events.own_member(request.user)
    if member is None or not events.can_join_team(request.user):
        raise PermissionDenied
    return member


def _decider(request: HttpRequest) -> None:
    if not services.can_decide(request.user):
        raise PermissionDenied


def _month(year: int, month: int) -> date:
    try:
        return date(year, month, 1)
    except ValueError as error:
        raise Http404 from error


# Eigene Abrechnung (Übungsleiter)


@login_required
def billing_index(request: HttpRequest) -> HttpResponse:
    if not events.can_join_team(request.user):
        if services.can_decide(request.user):
            return redirect("claim_list")
        raise PermissionDenied
    member = _own_member(request)
    months = services.months(member)
    return render(
        request,
        "billing/index.html",
        {
            "months": months,
            "pending": services.pending_confirmations(months),
            "now": timezone.now(),
            "deadline_day": services.DEADLINE_DAY,
        },
    )


@login_required
def billing_month(request: HttpRequest, year: int, month: int) -> HttpResponse:
    member = _own_member(request)
    overview = services.month_overview(member, _month(year, month))
    return render(
        request,
        "billing/month.html",
        {"overview": overview, "can_decide": services.can_decide(request.user), "now": timezone.now()},
    )


@require_POST
@login_required
def billing_submit(request: HttpRequest, year: int, month: int) -> HttpResponse:
    member = _own_member(request)
    try:
        claim = services.submit(member, _month(year, month), _user(request))
    except BillingError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, f"{claim.month_label} ist eingereicht.")
    return redirect("billing_month", year=year, month=month)


# Abrechnungen (Abteilungsleitung)


@login_required
def claim_list(request: HttpRequest) -> HttpResponse:
    _decider(request)
    months = services.claim_months()
    form = ClaimFilterForm(request.GET or None, months=months)
    month = status = None
    if form.is_valid():
        if form.cleaned_data["month"]:
            year, number = form.cleaned_data["month"].split("-")
            month = _month(int(year), int(number))
        status = form.cleaned_data["status"] or None
    rows = services.claims(month, status)
    pending = [] if month or status else list(services.pending_claims())
    if pending:
        rows = rows.exclude(status=ClaimStatus.SUBMITTED)
    return render(
        request,
        "billing/claim_list.html",
        {
            "form": form,
            "pending": pending,
            "claims": rows[:200],
            "month": month,
            "csv_months": [m for m in months if services.approved_for_month(m).exists()][:6],
        },
    )


def _claim(request: HttpRequest, pk: int) -> Claim:
    claim = get_object_or_404(Claim.objects.select_related("member"), pk=pk)
    if not services.can_decide(request.user) and events.own_member(request.user) != claim.member:
        raise PermissionDenied
    return claim


@login_required
def claim_detail(request: HttpRequest, pk: int) -> HttpResponse:
    claim = _claim(request, pk)
    return render(
        request,
        "billing/claim_detail.html",
        {
            "claim": claim,
            "lines": claim.lines.all(),
            "can_decide": services.can_decide(request.user),
            "send_back_form": SendBackForm(),
            "deadline": services.deadline(claim.month),
        },
    )


@require_POST
@login_required
def claim_approve(request: HttpRequest, pk: int) -> HttpResponse:
    _decider(request)
    claim = get_object_or_404(Claim, pk=pk)
    try:
        services.approve(claim, _user(request))
    except BillingError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, f"Die Abrechnung von {claim.member.display_name} ist freigegeben.")
    return redirect("claim_detail", pk=pk)


@require_POST
@login_required
def claim_send_back(request: HttpRequest, pk: int) -> HttpResponse:
    _decider(request)
    claim = get_object_or_404(Claim, pk=pk)
    form = SendBackForm(request.POST)
    try:
        if not form.is_valid():
            raise BillingError("Schreib bitte kurz, was geändert werden soll.")
        services.send_back(claim, _user(request), form.cleaned_data["feedback"])
    except BillingError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, f"Die Abrechnung ist an {claim.member.display_name} zurückgegeben.")
    return redirect("claim_detail", pk=pk)


@login_required
def claim_pdf(request: HttpRequest, pk: int) -> HttpResponse:
    claim = _claim(request, pk)
    if claim.status != ClaimStatus.APPROVED:
        raise Http404
    name = f"abrechnung-{claim.month:%Y-%m}-{claim.member.last_name.lower()}.pdf"
    response = HttpResponse(pdf.render(claim), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{name}"'
    return response


@login_required
def claim_csv(request: HttpRequest, year: int, month: int) -> HttpResponse:
    """Alle freigegebenen Abrechnungen eines Monats für die Geschäftsstelle (Semikolon, Excel-tauglich)."""
    _decider(request)
    day = _month(year, month)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="abrechnung-{day:%Y-%m}.csv"'
    response.write("﻿")
    writer = csv.writer(response, delimiter=";", lineterminator="\r\n")
    writer.writerow(
        ["Monat", "Nachname", "Vorname", "Mitgliedsnummer", "Stunden", "Betrag (€)", "Freigegeben am", "Verspätet"]
    )
    for claim in services.approved_for_month(day):
        writer.writerow(
            [
                f"{day:%m/%Y}",
                claim.member.last_name,
                claim.member.first_name,
                claim.member.member_number or "",
                formats.number_format(claim.hours, 2),
                formats.number_format(claim.total_amount, 2),
                formats.date_format(timezone.localtime(claim.decided_at), "d.m.Y") if claim.decided_at else "",
                "ja" if claim.is_late else "nein",
            ]
        )
    return response


# Stundensätze (Abteilungsleitung)


@login_required
def rate_list(request: HttpRequest) -> HttpResponse:
    _decider(request)
    rows = services.rate_table()
    return render(
        request,
        "billing/rate_list.html",
        {"rows": rows, "roles": [role for role in services.billable_roles() if role.is_team]},
    )


@login_required
def rate_member(request: HttpRequest, member_pk: int) -> HttpResponse:
    _decider(request)
    row = next((row for row in services.rate_table() if row.member.pk == member_pk), None)
    if row is None:
        raise Http404
    roles = [role for role, _ in row.rates]
    form = RateForm(request.POST or None, instance=Rate(member=row.member), roles=roles)
    if request.method == "POST" and form.is_valid():
        rate = form.save()
        audit.log(
            request.user,
            audit.Area.BILLING,
            "rate",
            f"Satz für {row.member.display_name}: {rate.role.name} {rate.hourly_rate} € ab {rate.valid_from:%d.%m.%Y}",
            member=row.member,
        )
        messages.success(request, f"Satz für {rate.role.name} ab {rate.valid_from:%d.%m.%Y} gespeichert.")
        return redirect("rate_member", member_pk=member_pk)
    return render(
        request,
        "billing/rate_member.html",
        {"row": row, "form": form, "history": services.rate_history(row.member)},
    )


@require_POST
@login_required
def rate_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Einen falsch eingetragenen Satz löschen. Eingereichte Abrechnungen behalten ihren Satz (Schnappschuss)."""
    _decider(request)
    rate = get_object_or_404(Rate, pk=pk)
    member_pk = rate.member_id
    rate.delete()
    audit.log(
        request.user,
        audit.Area.BILLING,
        "rate_delete",
        f"Satz für {rate.member.display_name} gelöscht: {rate.role.name} ab {rate.valid_from:%d.%m.%Y}",
        member=member_pk,
    )
    messages.success(request, "Der Satz ist gelöscht.")
    return redirect("rate_member", member_pk=member_pk)
