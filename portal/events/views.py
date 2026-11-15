from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from portal.accounts.models import Role, User
from portal.accounts.permissions import role_required
from portal.members import services as members
from portal.members.models import Member

from . import services
from .forms import (
    CancelRangeForm,
    ConfirmForm,
    EventForm,
    NoteForm,
    OccurrenceForm,
    RegisterForm,
    ScheduleForm,
    StaffForm,
    TargetGroupForm,
)
from .models import Event, EventStaff, Occurrence, Registration, Schedule, StaffFunction, Staffing, TargetGroup
from .services import MANAGE_EVENTS, Match, RegistrationError


def _user(request: HttpRequest) -> User:
    return request.user  # type: ignore[return-value]


def _errors(request: HttpRequest, form: Any) -> None:
    for errors in form.errors.values():
        for error in errors:
            messages.error(request, str(error))


# Termine für Mitglieder und Eltern


@login_required
def agenda(request: HttpRequest) -> HttpResponse:
    """Die nächsten Termine je eigenem Mitglied. Ohne eigene Mitglieder: alle Termine zur Übersicht."""
    sections = services.agenda(request.user)
    context: dict[str, Any] = {"sections": sections, "several": len(sections) > 1}
    if not sections:
        services.ensure_generated()
        context["occurrences"] = services.upcoming()
    return render(request, "events/agenda.html", context)


def _own_member(request: HttpRequest, member_pk: int) -> Member:
    member = get_object_or_404(Member, pk=member_pk)
    if not members.can_self_edit(request.user, member):
        raise PermissionDenied
    return member


@login_required
def occurrence_detail(request: HttpRequest, pk: int) -> HttpResponse:
    occurrence = get_object_or_404(Occurrence.objects.select_related("event", "schedule"), pk=pk)
    user = _user(request)
    on = timezone.localdate(occurrence.starts_at)
    window = services.window(occurrence)
    own = []
    for link in members.effective_links(user):
        registration = Registration.objects.filter(occurrence=occurrence, member=link.member).first()
        match = services.match_event(occurrence.event, link.member, on)
        own.append((link, services.AgendaItem(occurrence, match, registration, window)))
    lead = services.can_lead(user, occurrence)
    show_participants = services.can_see_participants(user, occurrence)
    staffings = list(occurrence.staffings.select_related("user"))
    own_staffing = next((staffing for staffing in staffings if staffing.user_id == user.pk), None)
    context = {
        "occurrence": occurrence,
        "event": occurrence.event,
        "window": window,
        "own": own,
        "staffings": staffings,
        "own_staffing": own_staffing,
        "lead": lead,
        "can_manage": services.can_manage_events(user),
        "is_trainer": services.is_trainer(user),
        "started": occurrence.starts_at <= timezone.now(),
        "participants": services.participants(occurrence) if show_participants else None,
        "registered": services.registered_count(occurrence),
    }
    if lead:
        context["note_form"] = NoteForm(instance=occurrence)
        context["staff_form"] = StaffForm(trainers=services.trainers())
    elif services.is_trainer(user) and not own_staffing:
        context["self_staff_functions"] = StaffFunction.choices
    if own_staffing and not own_staffing.is_confirmed:
        context["confirm_form"] = ConfirmForm(initial={"minutes": occurrence.minutes})
    return render(request, "events/occurrence_detail.html", context)


@login_required
def register(request: HttpRequest, pk: int, member_pk: int) -> HttpResponse:
    """Anmelden: mit einem Klick (POST) oder über das Formular, wenn das Gewicht Pflicht ist."""
    occurrence = get_object_or_404(Occurrence.objects.select_related("event"), pk=pk)
    member = _own_member(request, member_pk)
    event = occurrence.event
    try:
        services.check_register(occurrence, member)
    except RegistrationError as error:
        messages.error(request, str(error))
        return redirect(_next(request, occurrence))
    form = RegisterForm(
        request.POST if request.method == "POST" and "form" in request.POST else None,
        weight_required=event.weight_required,
        initial={"weight": member.weight},
    )
    quick = request.method == "POST" and "form" not in request.POST and not event.weight_required
    if quick or form.is_valid():
        data = form.cleaned_data if not quick else {}
        try:
            registration = services.register(
                occurrence, member, _user(request), weight=data.get("weight"), note=data.get("note", "")
            )
        except RegistrationError as error:
            messages.error(request, str(error))
        else:
            if registration.status == "waitlist":
                messages.info(request, f"{member.first_name} steht auf der Warteliste.")
            else:
                messages.success(request, f"{member.first_name} ist angemeldet.")
        return redirect(_next(request, occurrence))
    match = services.match_event(event, member, timezone.localdate(occurrence.starts_at))
    return render(
        request,
        "events/register.html",
        {"occurrence": occurrence, "member": member, "form": form, "maybe": match == Match.MAYBE},
    )


@require_POST
@login_required
def unregister(request: HttpRequest, pk: int, member_pk: int) -> HttpResponse:
    occurrence = get_object_or_404(Occurrence, pk=pk)
    member = _own_member(request, member_pk)
    registration = get_object_or_404(Registration, occurrence=occurrence, member=member)
    try:
        services.unregister(registration, _user(request))
    except RegistrationError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, f"{member.first_name} ist abgemeldet.")
    return redirect(_next(request, occurrence))


def _next(request: HttpRequest, occurrence: Occurrence) -> str:
    target = request.POST.get("next") or request.GET.get("next") or ""
    if target.startswith("/") and not target.startswith("//"):
        return target
    return reverse("occurrence_detail", args=[occurrence.pk])


# Termin leiten (Abteilungsleitung, begleitende Übungsleiter)


def _lead_occurrence(request: HttpRequest, pk: int) -> Occurrence:
    occurrence = get_object_or_404(Occurrence.objects.select_related("event"), pk=pk)
    if not services.can_lead(request.user, occurrence):
        raise PermissionDenied
    return occurrence


@login_required
def occurrence_edit(request: HttpRequest, pk: int) -> HttpResponse:
    occurrence = _lead_occurrence(request, pk)
    form = OccurrenceForm(request.POST or None, instance=occurrence)
    if request.method == "POST" and form.is_valid():
        services.update_occurrence(form.save(commit=False), form.changed_data, _user(request))
        messages.success(request, "Termin gespeichert.")
        return redirect("occurrence_detail", pk=occurrence.pk)
    return render(request, "events/occurrence_edit.html", {"occurrence": occurrence, "form": form})


@require_POST
@login_required
def occurrence_note(request: HttpRequest, pk: int) -> HttpResponse:
    occurrence = _lead_occurrence(request, pk)
    form = NoteForm(request.POST, instance=occurrence)
    if form.is_valid():
        form.save()
        messages.success(request, "Hinweis gespeichert.")
    return redirect("occurrence_detail", pk=occurrence.pk)


@require_POST
@login_required
def occurrence_cancel(request: HttpRequest, pk: int) -> HttpResponse:
    occurrence = _lead_occurrence(request, pk)
    if request.POST.get("undo"):
        if not services.can_manage_events(request.user):
            raise PermissionDenied
        services.uncancel(occurrence)
        messages.success(request, "Der Termin findet wieder statt.")
    else:
        services.cancel(occurrence, _user(request))
        messages.success(request, "Termin abgesagt. Angemeldete und Team bekommen eine Mail.")
    return redirect("occurrence_detail", pk=occurrence.pk)


@require_POST
@login_required
def occurrence_staff(request: HttpRequest, pk: int) -> HttpResponse:
    """Team eines Termins: Begleiter ändern beliebige Einträge, Übungsleiter tragen sich selbst ein."""
    occurrence = get_object_or_404(Occurrence, pk=pk)
    user = _user(request)
    if services.can_lead(user, occurrence):
        form = StaffForm(request.POST, trainers=services.trainers())
        if not form.is_valid():
            _errors(request, form)
            return redirect("occurrence_detail", pk=pk)
        target, function = form.cleaned_data["user"], form.cleaned_data["function"]
    elif services.is_trainer(user):
        target, function = user, request.POST.get("function", StaffFunction.CO_TRAINER)
        if function not in StaffFunction.values:
            raise PermissionDenied
    else:
        raise PermissionDenied
    try:
        services.set_staffing(occurrence, target, function)
    except ValueError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, f"{target.display_name} ist als {StaffFunction(function).label} eingetragen.")
    return redirect("occurrence_detail", pk=pk)


@require_POST
@login_required
def occurrence_staff_remove(request: HttpRequest, pk: int, staffing_pk: int) -> HttpResponse:
    staffing = get_object_or_404(
        Staffing.objects.select_related("occurrence", "user"), pk=staffing_pk, occurrence_id=pk
    )
    user = _user(request)
    if staffing.user_id != user.pk and not services.can_lead(user, staffing.occurrence):
        raise PermissionDenied
    try:
        services.remove_staffing(staffing)
    except ValueError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, f"{staffing.user.display_name} ist ausgetragen.")
    return redirect("occurrence_detail", pk=pk)


@require_POST
@login_required
def staffing_confirm(request: HttpRequest, pk: int) -> HttpResponse:
    staffing = get_object_or_404(Staffing.objects.select_related("occurrence"), occurrence_id=pk, user=request.user)
    form = ConfirmForm(request.POST)
    if not form.is_valid():
        _errors(request, form)
        return redirect("occurrence_detail", pk=pk)
    try:
        services.confirm(staffing, form.cleaned_data["minutes"])
    except ValueError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "Danke, deine Begleitung ist bestätigt.")
    return redirect(_next(request, staffing.occurrence))


@login_required
def participant_add(request: HttpRequest, pk: int) -> HttpResponse:
    """Ausnahme: ein Mitglied anmelden, das nicht zur Zielgruppe passt oder nach dem Anmeldeschluss kommt."""
    occurrence = _lead_occurrence(request, pk)
    if not services.can_see_participants(request.user, occurrence):
        raise PermissionDenied
    if request.method == "POST":
        member = get_object_or_404(Member, pk=request.POST.get("member"))
        try:
            services.register(occurrence, member, _user(request), exception=True)
        except RegistrationError as error:
            messages.error(request, str(error))
        else:
            messages.success(request, f"{member.display_name} ist angemeldet (Ausnahme).")
        return redirect("occurrence_detail", pk=pk)
    query = request.GET.get("q", "").strip()
    results: list[Member] = []
    if len(query) >= 2:
        found = Member.objects.filter(Q(first_name__icontains=query) | Q(last_name__icontains=query))
        results = [member for member in found[:30] if member.is_active]
    return render(
        request, "events/participant_add.html", {"occurrence": occurrence, "query": query, "results": results}
    )


@require_POST
@login_required
def participant_remove(request: HttpRequest, pk: int, registration_pk: int) -> HttpResponse:
    occurrence = _lead_occurrence(request, pk)
    registration = get_object_or_404(Registration, pk=registration_pk, occurrence=occurrence)
    services.unregister(registration, _user(request), force=True)
    messages.success(request, f"{registration.member.display_name} ist abgemeldet.")
    return redirect("occurrence_detail", pk=pk)


# Meine Einsätze (Übungsleiter)


@role_required(Role.TRAINER)
def my_staffings(request: HttpRequest) -> HttpResponse:
    services.ensure_generated()
    coming, past = services.own_staffings(_user(request))
    return render(
        request,
        "events/my_staffings.html",
        {"coming": coming, "past": past, "now": timezone.now()},
    )


# Veranstaltungen verwalten


def _plan_staff(request: HttpRequest) -> None:
    if not services.can_plan_staff(request.user):
        raise PermissionDenied


@login_required
def event_list(request: HttpRequest) -> HttpResponse:
    _plan_staff(request)
    services.ensure_generated()
    now = timezone.now()
    rows = []
    for event in Event.objects.prefetch_related("target_groups", "schedules"):
        upcoming = event.occurrences.filter(ends_at__gte=now, cancelled_at__isnull=True).first()
        rows.append((event, upcoming))
    return render(
        request,
        "events/event_list.html",
        {"rows": rows, "can_manage": services.can_manage_events(request.user)},
    )


@login_required
def event_detail(request: HttpRequest, pk: int) -> HttpResponse:
    _plan_staff(request)
    event = get_object_or_404(Event.objects.prefetch_related("target_groups", "staff__user"), pk=pk)
    services.ensure_generated()
    occurrences = event.occurrences.filter(ends_at__gte=timezone.now()).prefetch_related("staffings__user")[:20]
    context = {
        "event": event,
        "schedules": event.schedules.all(),
        "occurrences": occurrences,
        "can_manage": services.can_manage_events(request.user),
        "staff_form": StaffForm(trainers=services.trainers()),
        "cancel_form": CancelRangeForm(),
    }
    return render(request, "events/event_detail.html", context)


@role_required(*MANAGE_EVENTS)
def event_edit(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    event = get_object_or_404(Event, pk=pk) if pk else None
    form = EventForm(request.POST or None, instance=event)
    if request.method == "POST" and form.is_valid():
        event = form.save()
        messages.success(request, f"„{event.title}“ gespeichert.")
        return redirect("event_detail", pk=event.pk)
    return render(request, "events/event_edit.html", {"form": form, "event": event})


@require_POST
@role_required(*MANAGE_EVENTS)
def event_delete(request: HttpRequest, pk: int) -> HttpResponse:
    event = get_object_or_404(Event, pk=pk)
    if Staffing.objects.filter(occurrence__event=event, confirmed_at__isnull=False).exists():
        messages.error(request, "Die Veranstaltung hat bestätigte Begleitungen und bleibt für die Abrechnung erhalten.")
        return redirect("event_detail", pk=pk)
    event.delete()
    messages.success(request, f"„{event.title}“ gelöscht.")
    return redirect("event_list")


@role_required(*MANAGE_EVENTS)
def schedule_edit(request: HttpRequest, pk: int, schedule_pk: int | None = None) -> HttpResponse:
    event = get_object_or_404(Event, pk=pk)
    schedule = get_object_or_404(Schedule, pk=schedule_pk, event=event) if schedule_pk else None
    form = ScheduleForm(request.POST or None, instance=schedule)
    if request.method == "POST" and form.is_valid():
        saved = form.save(commit=False)
        saved.event = event
        saved.save()
        if schedule:
            kept = services.regenerate(saved)
            if kept:
                dates = ", ".join(f"{timezone.localtime(o.starts_at):%d.%m.}" for o in kept)
                messages.warning(
                    request, f"Diese Termine haben Anmeldungen oder Abweichungen und bleiben, wie sie sind: {dates}."
                )
        else:
            services.generate(saved)
        messages.success(request, f"Zeitplan „{saved}“ gespeichert.")
        return redirect("event_detail", pk=event.pk)
    return render(request, "events/schedule_edit.html", {"form": form, "event": event, "schedule": schedule})


@require_POST
@role_required(*MANAGE_EVENTS)
def schedule_delete(request: HttpRequest, pk: int, schedule_pk: int) -> HttpResponse:
    schedule = get_object_or_404(Schedule, pk=schedule_pk, event_id=pk)
    kept = services.delete_schedule(schedule)
    messages.success(
        request,
        "Zeitplan gelöscht." + (f" {kept} Termine mit Anmeldungen bleiben als Einzeltermine." if kept else ""),
    )
    return redirect("event_detail", pk=pk)


@role_required(*MANAGE_EVENTS)
def occurrence_create(request: HttpRequest, pk: int) -> HttpResponse:
    event = get_object_or_404(Event, pk=pk)
    form = OccurrenceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        occurrence = form.save(commit=False)
        occurrence.event = event
        occurrence.save()
        services.add_default_staff(occurrence)
        messages.success(request, "Termin angelegt.")
        return redirect("event_detail", pk=event.pk)
    return render(request, "events/occurrence_edit.html", {"form": form, "event": event, "occurrence": None})


@require_POST
@role_required(*MANAGE_EVENTS)
def event_cancel_range(request: HttpRequest, pk: int) -> HttpResponse:
    event = get_object_or_404(Event, pk=pk)
    form = CancelRangeForm(request.POST)
    if not form.is_valid():
        _errors(request, form)
    else:
        count = services.cancel_range(event, form.cleaned_data["first"], form.cleaned_data["last"], _user(request))
        messages.success(request, f"{count} Termin{'e' if count != 1 else ''} abgesagt.")
    return redirect("event_detail", pk=pk)


@require_POST
@login_required
def event_staff(request: HttpRequest, pk: int) -> HttpResponse:
    _plan_staff(request)
    event = get_object_or_404(Event, pk=pk)
    form = StaffForm(request.POST, trainers=services.trainers())
    if not form.is_valid():
        _errors(request, form)
    else:
        try:
            services.set_default_staff(event, form.cleaned_data["user"], form.cleaned_data["function"])
        except ValueError as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "Standard-Team gespeichert; kommende Termine übernehmen es.")
    return redirect("event_detail", pk=pk)


@require_POST
@login_required
def event_staff_remove(request: HttpRequest, pk: int, staff_pk: int) -> HttpResponse:
    _plan_staff(request)
    staff = get_object_or_404(EventStaff.objects.select_related("user"), pk=staff_pk, event_id=pk)
    services.remove_default_staff(staff)
    messages.success(request, f"{staff.user.display_name} ist nicht mehr im Standard-Team.")
    return redirect("event_detail", pk=pk)


# Zielgruppen


@role_required(*MANAGE_EVENTS)
def target_group_list(request: HttpRequest) -> HttpResponse:
    groups = [
        (group, len(services.matching_members(group))) for group in TargetGroup.objects.prefetch_related("interests")
    ]
    return render(request, "events/target_group_list.html", {"groups": groups})


@role_required(*MANAGE_EVENTS)
def target_group_edit(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    group = get_object_or_404(TargetGroup, pk=pk) if pk else None
    form = TargetGroupForm(request.POST or None, instance=group)
    if request.method == "POST" and form.is_valid():
        group = form.save()
        count = len(services.matching_members(group))
        messages.success(request, f"Zielgruppe „{group.name}“ gespeichert. Aktuell passen {count} Mitglieder.")
        return redirect("target_group_members", pk=group.pk)
    return render(request, "events/target_group_edit.html", {"form": form, "group": group})


@role_required(*MANAGE_EVENTS)
def target_group_members(request: HttpRequest, pk: int) -> HttpResponse:
    group = get_object_or_404(TargetGroup, pk=pk)
    return render(
        request,
        "events/target_group_members.html",
        {"group": group, "rows": services.matching_members(group), "maybe": Match.MAYBE},
    )


@require_POST
@role_required(*MANAGE_EVENTS)
def target_group_delete(request: HttpRequest, pk: int) -> HttpResponse:
    group = get_object_or_404(TargetGroup, pk=pk)
    group.delete()
    messages.success(request, f"Zielgruppe „{group.name}“ gelöscht.")
    return redirect("target_group_list")
