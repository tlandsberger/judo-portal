from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from portal.accounts.models import User
from portal.accounts.permissions import role_required
from portal.members import services as members
from portal.members.models import Member

from . import guests, services
from .forms import (
    AbsentForm,
    CancelRangeForm,
    ConfirmForm,
    EventCreateForm,
    EventForm,
    EventTypeForm,
    GuestForm,
    GuestRegisterForm,
    NoteForm,
    OccurrenceForm,
    ParticipantRoleForm,
    RegisterForm,
    ScheduleForm,
    TargetGroupFormSet,
    TargetGroupTemplateForm,
    TeamForm,
)
from .models import (
    Event,
    EventType,
    Guest,
    Occurrence,
    ParticipantRole,
    Participation,
    Schedule,
    ScheduleTeam,
    TargetGroupTemplate,
)
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
    """Die nächsten Termine, jeder einmal, mit den eigenen Mitgliedern. Ohne eigene Mitglieder: alle zur Übersicht."""
    result = services.agenda(request.user)
    context: dict[str, Any] = {"agenda": result}
    if result is None:
        services.ensure_generated()
        context["occurrences"] = services.upcoming()
    return render(request, "events/agenda.html", context)


def _own_member(request: HttpRequest, member_pk: int) -> Member:
    member = get_object_or_404(Member, pk=member_pk)
    if not members.can_self_edit(request.user, member):
        raise PermissionDenied
    return member


def _team_form(event: Event, data: Any = None, prefix: str | None = None) -> TeamForm:
    return TeamForm(data, prefix=prefix, candidates=services.team_candidates(event), roles=services.team_roles(event))


@login_required
def occurrence_detail(request: HttpRequest, pk: int) -> HttpResponse:
    occurrence = get_object_or_404(Occurrence.objects.select_related("event", "schedule"), pk=pk)
    user = _user(request)
    on = timezone.localdate(occurrence.starts_at)
    window = services.window(occurrence)
    own = []
    for link in members.effective_links(user):
        participation = (
            Participation.objects.filter(occurrence=occurrence, member=link.member).select_related("role").first()
        )
        match = services.match_event(occurrence.event, link.member, on)
        own.append((link, services.AgendaItem(occurrence, match, participation, window)))
    lead = services.can_lead(user, occurrence)
    show_participants = services.can_see_participants(user, occurrence)
    team = services.team(occurrence)
    member = services.own_member(user)
    own_team = next((p for p in team if member and p.member_id == member.pk), None)
    context = {
        "occurrence": occurrence,
        "event": occurrence.event,
        "window": window,
        "own": own,
        "team": team,
        "own_team": own_team,
        "lead": lead,
        "can_manage": services.can_manage_events(user),
        "can_join_team": services.can_join_team(user),
        "started": occurrence.starts_at <= timezone.now(),
        "participants": services.participants(occurrence) if show_participants else None,
        "registered": services.registered_count(occurrence),
    }
    if lead:
        context["note_form"] = NoteForm(instance=occurrence)
        context["team_form"] = _team_form(occurrence.event)
    elif member and not own_team:
        context["self_roles"] = [
            role
            for role in services.team_roles(occurrence.event)
            if services.can_take_role(member, role, occurrence.event)
        ]
    if own_team and own_team.role.is_billable and not own_team.is_confirmed:
        context["confirm_form"] = ConfirmForm(initial={"minutes": occurrence.minutes})
    if own_team and own_team.is_confirmed and not services.locked_reason(own_team):
        context["can_unconfirm"] = True
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
            participation = services.register(
                occurrence, member, _user(request), weight=data.get("weight"), note=data.get("note", "")
            )
        except RegistrationError as error:
            messages.error(request, str(error))
        else:
            if participation.status == "waitlist":
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
    participation = get_object_or_404(Participation, occurrence=occurrence, member=member, role__is_team=False)
    try:
        services.unregister(participation, _user(request))
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


# Termin leiten (Abteilungsleitung, Team des Termins)


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
        services.uncancel(occurrence, _user(request))
        messages.success(request, "Der Termin findet wieder statt.")
    else:
        services.cancel(occurrence, _user(request))
        messages.success(request, "Termin abgesagt. Angemeldete und Übungsleiter bekommen eine Mail.")
    return redirect("occurrence_detail", pk=occurrence.pk)


@require_POST
@login_required
def occurrence_team(request: HttpRequest, pk: int) -> HttpResponse:
    """Team eines Termins: wer den Termin leitet, trägt beliebige Mitglieder ein; sonst trägt man sich selbst ein."""
    occurrence = get_object_or_404(Occurrence.objects.select_related("event"), pk=pk)
    user = _user(request)
    if services.can_lead(user, occurrence) and "member" in request.POST:
        form = _team_form(occurrence.event, request.POST)
        if not form.is_valid():
            _errors(request, form)
            return redirect("occurrence_detail", pk=pk)
        member, role = form.cleaned_data["member"], form.cleaned_data["role"]
    else:
        member = services.own_member(user)
        role = ParticipantRole.objects.filter(pk=request.POST.get("role", 0), is_team=True).first()
        if member is None or role is None:
            raise PermissionDenied
    try:
        services.set_team(occurrence, member, role, user)
    except RegistrationError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, f"{member.display_name} ist als {role.name} eingetragen.")
    return redirect("occurrence_detail", pk=pk)


@require_POST
@login_required
def occurrence_team_remove(request: HttpRequest, pk: int, participation_pk: int) -> HttpResponse:
    participation = get_object_or_404(
        Participation.objects.select_related("occurrence", "member", "role"),
        pk=participation_pk,
        occurrence_id=pk,
        role__is_team=True,
    )
    user = _user(request)
    member = services.own_member(user)
    is_self = member is not None and participation.member_id == member.pk
    if not is_self and not services.can_lead(user, participation.occurrence):
        raise PermissionDenied
    try:
        services.remove_team(participation, _user(request))
    except RegistrationError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, f"{participation.person.display_name} ist ausgetragen.")
    return redirect("occurrence_detail", pk=pk)


@require_POST
@login_required
def hours_confirm(request: HttpRequest, pk: int) -> HttpResponse:
    member = services.own_member(request.user)
    participation = get_object_or_404(
        Participation.objects.select_related("occurrence", "role"), occurrence_id=pk, member=member, role__is_team=True
    )
    form = ConfirmForm(request.POST)
    if not form.is_valid():
        _errors(request, form)
        return redirect("occurrence_detail", pk=pk)
    corrected = participation.is_confirmed
    try:
        services.confirm(participation, form.cleaned_data["minutes"], by=_user(request))
    except RegistrationError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "Die Dauer ist geändert." if corrected else "Danke, deine Stunden sind bestätigt.")
    return redirect(_next(request, participation.occurrence))


@login_required
def hours_absent(request: HttpRequest, pk: int) -> HttpResponse:
    """„Nicht dabei?“: Team-Teilnahme nachträglich austragen, an eine Vertretung übertragen oder Termin absagen."""
    member = services.own_member(request.user)
    participation = get_object_or_404(
        Participation.objects.select_related("occurrence__event", "role"),
        occurrence_id=pk,
        member=member,
        role__is_team=True,
        status__in=services.ACTIVE,
    )
    occurrence = participation.occurrence
    roles = services.team_roles(occurrence.event)
    candidates = [m for m in services.team_candidates(occurrence.event) if m != member]
    form = AbsentForm(request.POST or None, candidates=candidates, roles=roles, initial={"role": participation.role_id})
    locked = services.locked_reason(participation)
    if request.method == "POST" and not locked and form.is_valid():
        user = _user(request)
        what = form.cleaned_data["what"]
        try:
            if what == AbsentForm.HAND_OVER:
                substitute = form.cleaned_data["member"]
                services.hand_over(participation, substitute, form.cleaned_data["role"], user)
                messages.success(request, f"Übertragen: {substitute.display_name} bekommt die Stunden zum Bestätigen.")
            elif what == AbsentForm.CANCEL:
                services.cancel_after(occurrence, user)
                messages.success(request, "Der Termin ist nachträglich abgesagt.")
            else:
                services.withdraw(participation, user)
                messages.success(request, "Du bist als Übungsleiter des Termins ausgetragen.")
        except RegistrationError as error:
            messages.error(request, str(error))
        else:
            return redirect("billing_index")
    return render(
        request,
        "events/hours_absent.html",
        {
            "participation": participation,
            "occurrence": occurrence,
            "form": form,
            "locked": locked,
            "started": occurrence.starts_at <= timezone.now(),
        },
    )


@require_POST
@login_required
def hours_unconfirm(request: HttpRequest, pk: int) -> HttpResponse:
    member = services.own_member(request.user)
    participation = get_object_or_404(
        Participation.objects.select_related("occurrence__event", "role"),
        occurrence_id=pk,
        member=member,
        role__is_team=True,
    )
    try:
        services.unconfirm(participation, by=_user(request))
    except RegistrationError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "Die Bestätigung ist zurückgenommen.")
    return redirect(_next(request, participation.occurrence))


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
def participant_remove(request: HttpRequest, pk: int, participation_pk: int) -> HttpResponse:
    occurrence = _lead_occurrence(request, pk)
    participation = get_object_or_404(Participation, pk=participation_pk, occurrence=occurrence, role__is_team=False)
    services.unregister(participation, _user(request), force=True)
    messages.success(request, f"{participation.person.display_name} ist abgemeldet.")
    return redirect("occurrence_detail", pk=pk)


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
    for event in Event.objects.select_related("event_type").prefetch_related("target_groups__interests", "schedules"):
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
    event = get_object_or_404(
        Event.objects.select_related("event_type").prefetch_related("target_groups__interests"), pk=pk
    )
    services.ensure_generated()
    occurrences = event.occurrences.filter(ends_at__gte=timezone.now()).prefetch_related(
        "participations__role", "participations__member"
    )[:20]
    schedules = list(event.schedules.prefetch_related("team__member", "team__role"))
    for schedule in schedules:
        schedule.team_form = _team_form(event, prefix=f"s{schedule.pk}")  # type: ignore[attr-defined]
    can_manage = services.can_manage_events(request.user)
    context = {
        "event": event,
        "matching": services.matching_members(event) if can_manage else None,
        "maybe": Match.MAYBE,
        "schedules": schedules,
        "occurrences": occurrences,
        "can_manage": can_manage,
        "cancel_form": CancelRangeForm(),
        "guest_link": request.build_absolute_uri(reverse("guest_register", args=[guests.enable_link(event)]))
        if event.guests_welcome
        else None,
    }
    return render(request, "events/event_detail.html", context)


@role_required(*MANAGE_EVENTS)
def event_edit(request: HttpRequest, pk: int) -> HttpResponse:
    event = get_object_or_404(Event, pk=pk)
    form = EventForm(request.POST or None, instance=event)
    groups = TargetGroupFormSet(request.POST or None, instance=event, prefix="zg")
    if request.method == "POST" and form.is_valid() and groups.is_valid():
        with transaction.atomic():
            event = form.save()
            templates = services.save_target_groups(groups)
        messages.success(request, f"„{event.title}“ gespeichert.{_templates_saved(templates)}")
        return redirect("event_detail", pk=event.pk)
    return render(
        request,
        "events/event_edit.html",
        {"form": form, "event": event, "groups": groups, "templates": services.template_data()},
    )


def _templates_saved(templates: list[TargetGroupTemplate]) -> str:
    if not templates:
        return ""
    names = ", ".join(f"„{template.name}“" for template in templates)
    return f" Neue Vorlage{'n' if len(templates) > 1 else ''}: {names}."


@role_required(*MANAGE_EVENTS)
def event_create(request: HttpRequest) -> HttpResponse:
    """Veranstaltung mit Terminen anlegen: einmalig, wiederkehrend oder später."""
    form = EventCreateForm(request.POST or None, candidates=services.team_candidates(), roles=services.team_roles())
    groups = TargetGroupFormSet(request.POST or None, instance=Event(), prefix="zg")
    if request.method == "POST" and form.is_valid() and groups.is_valid():
        data = form.cleaned_data
        team = (data["team_member"], data["team_role"]) if data.get("team_member") else None
        try:
            with transaction.atomic():
                event = form.save()
                groups.instance = event
                templates = services.save_target_groups(groups)
                occurrences = services.create_event(
                    event,
                    dates=data["dates"],
                    once={name: data[name] for name in form.ONCE_FIELDS},
                    weekly={name: data[name] for name in form.WEEKLY_FIELDS},
                    team=team,
                )
        except RegistrationError as error:
            form.add_error("team_role", str(error))
        else:
            count = len(occurrences)
            dates = f" mit {count} Termin{'en' if count != 1 else ''}" if count else ""
            messages.success(request, f"„{event.title}“ angelegt{dates}.{_templates_saved(templates)}")
            return redirect("event_detail", pk=event.pk)
    return render(
        request, "events/event_create.html", {"form": form, "groups": groups, "templates": services.template_data()}
    )


@require_POST
@role_required(*MANAGE_EVENTS)
def event_delete(request: HttpRequest, pk: int) -> HttpResponse:
    event = get_object_or_404(Event, pk=pk)
    if Participation.objects.filter(occurrence__event=event, confirmed_at__isnull=False).exists():
        messages.error(request, "Die Veranstaltung hat bestätigte Stunden und bleibt für die Abrechnung erhalten.")
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
        messages.success(request, "Termin angelegt. Trag hier die Übungsleiter ein.")
        return redirect("occurrence_detail", pk=occurrence.pk)
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
def schedule_team(request: HttpRequest, pk: int, schedule_pk: int) -> HttpResponse:
    _plan_staff(request)
    schedule = get_object_or_404(Schedule.objects.select_related("event"), pk=schedule_pk, event_id=pk)
    form = _team_form(schedule.event, request.POST, prefix=f"s{schedule.pk}")
    if not form.is_valid():
        _errors(request, form)
    else:
        try:
            services.set_schedule_team(schedule, form.cleaned_data["member"], form.cleaned_data["role"])
        except RegistrationError as error:
            messages.error(request, str(error))
        else:
            messages.success(
                request, f"Feste Übungsleiter für „{schedule}“ gespeichert; kommende Termine übernehmen sie."
            )
    return redirect("event_detail", pk=pk)


@require_POST
@login_required
def schedule_team_remove(request: HttpRequest, pk: int, schedule_pk: int, entry_pk: int) -> HttpResponse:
    _plan_staff(request)
    entry = get_object_or_404(
        ScheduleTeam.objects.select_related("member", "schedule"),
        pk=entry_pk,
        schedule_id=schedule_pk,
        schedule__event_id=pk,
    )
    services.remove_schedule_team(entry)
    messages.success(request, f"{entry.member.display_name} ist nicht mehr fest eingeteilt.")
    return redirect("event_detail", pk=pk)


# Gäste (ADR 0013)

GUEST_LIMIT = 10  # Anmeldungen je IP-Adresse und Stunde über den öffentlichen Link


def _too_many(request: HttpRequest) -> bool:
    key = f"guest-register:{request.META.get('REMOTE_ADDR', '')}"
    count = cache.get(key, 0)
    if count >= GUEST_LIMIT:
        return True
    cache.set(key, count + 1, 3600)
    return False


def guest_register(request: HttpRequest, token: str) -> HttpResponse:
    """Öffentliche Anmeldung für Gäste über den Link der Veranstaltung, ohne Zugang."""
    event = guests.event_for_link(token)
    if event is None:
        return render(request, "events/guest_link_invalid.html", status=404)
    occurrences = guests.open_occurrences(event)
    form = GuestRegisterForm(request.POST or None, event=event, occurrences=occurrences)
    if request.method == "POST" and form.is_valid():
        if _too_many(request):
            form.add_error(None, "Zu viele Anmeldungen von hier. Bitte versuch es später noch einmal.")
        else:
            data = {name: form.cleaned_data[name] for name in GuestForm.Meta.fields}
            try:
                guest = guests.register(event, data, form.cleaned_data["occurrences"])
            except RegistrationError as error:
                form.add_error(None, str(error))
            else:
                return render(request, "events/guest_register_done.html", {"event": event, "guest": guest})
    return render(request, "events/guest_register.html", {"event": event, "form": form, "occurrences": occurrences})


def guest_page(request: HttpRequest, token: str) -> HttpResponse:
    """Persönliche Seite eines Gastes: Termine, Daten, bestätigen, ab- und anmelden."""
    guest = Guest.objects.select_related("event").filter(token=token).first()
    if guest is None:
        return render(request, "events/guest_link_invalid.html", status=404)
    event = guest.event
    form = GuestForm(instance=guest, event=event)
    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "confirm":
                guests.confirm(guest)
                messages.success(request, "Danke! Deine Anmeldung ist bestätigt.")
            elif action == "cancel":
                participation = get_object_or_404(guest.participations, pk=request.POST.get("participation"))
                guests.unregister(participation)
                messages.success(request, "Du bist von diesem Termin abgemeldet.")
            elif action == "add":
                occurrence = get_object_or_404(event.occurrences, pk=request.POST.get("occurrence"))
                guests.add(guest, occurrence)
                messages.success(request, "Du bist für den Termin angemeldet.")
            elif action == "save":
                form = GuestForm(request.POST, instance=Guest.objects.get(pk=guest.pk), event=event)
                if form.is_valid():
                    guests.update(guest, {name: form.cleaned_data[name] for name in GuestForm.Meta.fields})
                    messages.success(request, "Deine Daten sind gespeichert.")
                else:
                    return _guest_page(request, guest, form)
        except RegistrationError as error:
            messages.error(request, str(error))
        return redirect("guest_page", token=token)
    return _guest_page(request, guest, form)


def _guest_page(request: HttpRequest, guest: Guest, form: GuestForm) -> HttpResponse:
    participations = list(guest.participations.select_related("occurrence__event").order_by("occurrence__starts_at"))
    taken = {p.occurrence_id for p in participations if p.status != "cancelled"}
    rows = [(p, services.window(p.occurrence)) for p in participations]
    more = [o for o in guests.open_occurrences(guest.event) if o.pk not in taken] if guest.confirmed_at else []
    return render(
        request,
        "events/guest_page.html",
        {"guest": guest, "event": guest.event, "rows": rows, "more": more, "form": form},
    )


@login_required
def guest_add(request: HttpRequest, pk: int) -> HttpResponse:
    """Das Team trägt einen Gast für einen Termin ein; der Gast bekommt eine Mail mit seinem Link."""
    occurrence = _lead_occurrence(request, pk)
    if not occurrence.event.guests_welcome:
        raise PermissionDenied
    form = GuestForm(request.POST or None, event=occurrence.event)
    if request.method == "POST" and form.is_valid():
        data = {name: form.cleaned_data[name] for name in GuestForm.Meta.fields}
        try:
            guest = guests.register(occurrence.event, data, [occurrence], by=_user(request))
        except RegistrationError as error:
            messages.error(request, str(error))
        else:
            messages.success(request, f"{guest.display_name} ist als Gast eingetragen und bekommt eine Mail.")
            return redirect("occurrence_detail", pk=pk)
    return render(request, "events/guest_add.html", {"occurrence": occurrence, "form": form})


@require_POST
@role_required(*MANAGE_EVENTS)
def event_guest_link(request: HttpRequest, pk: int) -> HttpResponse:
    event = get_object_or_404(Event, pk=pk)
    guests.renew_link(event)
    messages.success(request, "Neuer Anmeldelink erzeugt. Der alte gilt nicht mehr.")
    return redirect("event_detail", pk=pk)


# Veranstaltungsarten und Rollen


@role_required(*MANAGE_EVENTS)
def event_type_list(request: HttpRequest) -> HttpResponse:
    types = EventType.objects.annotate(count=Count("events"))
    return render(request, "events/event_type_list.html", {"types": types})


@role_required(*MANAGE_EVENTS)
def event_type_edit(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    event_type = get_object_or_404(EventType, pk=pk) if pk else None
    form = EventTypeForm(request.POST or None, instance=event_type)
    if request.method == "POST" and form.is_valid():
        event_type = form.save()
        messages.success(request, f"Veranstaltungsart „{event_type.name}“ gespeichert.")
        return redirect("event_type_list")
    return render(request, "events/event_type_edit.html", {"form": form, "event_type": event_type})


@require_POST
@role_required(*MANAGE_EVENTS)
def event_type_delete(request: HttpRequest, pk: int) -> HttpResponse:
    event_type = get_object_or_404(EventType, pk=pk)
    if event_type.events.exists() or event_type.roles.exists():
        messages.error(request, f"„{event_type.name}“ wird noch verwendet. Du kannst die Art deaktivieren.")
        return redirect("event_type_edit", pk=pk)
    event_type.delete()
    messages.success(request, f"Veranstaltungsart „{event_type.name}“ gelöscht.")
    return redirect("event_type_list")


@role_required(*MANAGE_EVENTS)
def role_list(request: HttpRequest) -> HttpResponse:
    roles = ParticipantRole.objects.prefetch_related("event_types")
    restricted = {value for role in roles if role.is_team for value in role.user_roles}
    return render(
        request,
        "events/role_list.html",
        {"roles": roles, "without_member": services.users_without_member(restricted)},
    )


@role_required(*MANAGE_EVENTS)
def role_edit(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    role = get_object_or_404(ParticipantRole, pk=pk) if pk else None
    form = ParticipantRoleForm(request.POST or None, instance=role)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            if form.cleaned_data["is_default"]:
                others = ParticipantRole.objects.filter(is_default=True)
                (others.exclude(pk=role.pk) if role else others).update(is_default=False)
            role = form.save()
        messages.success(request, f"Rolle „{role.name}“ gespeichert.")
        return redirect("role_list")
    return render(request, "events/role_edit.html", {"form": form, "role": role})


@require_POST
@role_required(*MANAGE_EVENTS)
def role_delete(request: HttpRequest, pk: int) -> HttpResponse:
    role = get_object_or_404(ParticipantRole, pk=pk)
    if role.is_default or role.participations.exists() or ScheduleTeam.objects.filter(role=role).exists():
        messages.error(request, f"„{role.name}“ wird noch verwendet. Du kannst die Rolle deaktivieren.")
        return redirect("role_edit", pk=pk)
    role.delete()
    messages.success(request, f"Rolle „{role.name}“ gelöscht.")
    return redirect("role_list")


# Zielgruppen-Vorlagen


@role_required(*MANAGE_EVENTS)
def target_group_list(request: HttpRequest) -> HttpResponse:
    groups = [
        (group, len(services.matching_members(group)))
        for group in TargetGroupTemplate.objects.prefetch_related("interests")
    ]
    return render(request, "events/target_group_list.html", {"groups": groups})


@role_required(*MANAGE_EVENTS)
def target_group_edit(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    group = get_object_or_404(TargetGroupTemplate, pk=pk) if pk else None
    form = TargetGroupTemplateForm(request.POST or None, instance=group)
    if request.method == "POST" and form.is_valid():
        group = form.save()
        count = len(services.matching_members(group))
        messages.success(request, f"Vorlage „{group.name}“ gespeichert. Aktuell passen {count} Mitglieder.")
        return redirect("target_group_members", pk=group.pk)
    return render(request, "events/target_group_edit.html", {"form": form, "group": group})


@role_required(*MANAGE_EVENTS)
def target_group_members(request: HttpRequest, pk: int) -> HttpResponse:
    group = get_object_or_404(TargetGroupTemplate, pk=pk)
    return render(
        request,
        "events/target_group_members.html",
        {"group": group, "rows": services.matching_members(group), "maybe": Match.MAYBE},
    )


@require_POST
@role_required(*MANAGE_EVENTS)
def target_group_delete(request: HttpRequest, pk: int) -> HttpResponse:
    group = get_object_or_404(TargetGroupTemplate, pk=pk)
    group.delete()
    messages.success(request, f"Vorlage „{group.name}“ gelöscht. Veranstaltungen behalten ihre Zielgruppen.")
    return redirect("target_group_list")
