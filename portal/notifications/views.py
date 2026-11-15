from __future__ import annotations

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from portal.accounts import devices
from portal.accounts.models import User

from . import services
from .models import PushSubscription


@require_POST
@login_required
def subscribe(request: HttpRequest) -> HttpResponse:
    """Abo aus ``pushManager.subscribe`` speichern (JSON, CSRF-Header)."""
    if not services.push_enabled():
        return HttpResponseBadRequest("Push ist nicht eingerichtet.")
    try:
        data = json.loads(request.body)
        endpoint, keys = str(data["endpoint"]), data["keys"]
        p256dh, auth = str(keys["p256dh"]), str(keys["auth"])
    except ValueError, KeyError, TypeError:
        return HttpResponseBadRequest("Ungültiges Abo.")
    if not endpoint.startswith("https://"):
        return HttpResponseBadRequest("Ungültiges Abo.")
    user: User = request.user  # type: ignore[assignment]
    services.subscribe(user, endpoint, p256dh, auth, devices.describe(request.headers.get("User-Agent", "")))
    return JsonResponse({"ok": True})


@require_POST
@login_required
def unsubscribe(request: HttpRequest) -> HttpResponse:
    try:
        endpoint = str(json.loads(request.body)["endpoint"])
    except ValueError, KeyError, TypeError:
        return HttpResponseBadRequest("Ungültiges Abo.")
    services.unsubscribe(request.user, endpoint)  # type: ignore[arg-type]
    return JsonResponse({"ok": True})


@require_POST
@login_required
def remove_device(request: HttpRequest, pk: int) -> HttpResponse:
    subscription = get_object_or_404(PushSubscription, pk=pk, user=request.user)
    subscription.delete()
    messages.success(request, f"Push für {subscription.device or 'das Gerät'} ist aus.")
    return redirect("security")


@require_POST
@login_required
def test(request: HttpRequest, pk: int) -> HttpResponse:
    subscription = get_object_or_404(PushSubscription, pk=pk, user=request.user)
    if services.send_test(subscription):
        messages.success(request, f"Test-Nachricht an {subscription.device or 'das Gerät'} verschickt.")
    else:
        messages.error(request, "Die Test-Nachricht kam nicht an. Schalte Push auf dem Gerät bitte neu ein.")
    return redirect("security")


@csrf_exempt
@require_POST
def action(request: HttpRequest) -> HttpResponse:
    """Knopf an einer Push-Nachricht. Der signierte Token ersetzt Anmeldung und CSRF-Token."""
    result = services.run_action(request.POST.get("token", ""))
    return JsonResponse({"ok": result.ok, "message": result.message, "url": result.url})
