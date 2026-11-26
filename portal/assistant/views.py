from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from . import services, tools
from .models import Conversation

SESSION_KEY = "assistant_conversation"


def _check(request: HttpRequest) -> None:
    if not services.can_use(request.user):
        raise Http404


def _conversation(request: HttpRequest) -> Conversation | None:
    return services.conversation(request.user, request.session.get(SESSION_KEY))


@login_required
def chat(request: HttpRequest) -> HttpResponse:
    """Chat mit Uke: nur das laufende Gespräch dieser Sitzung; ältere sieht man nicht (nur in der Auskunft)."""
    _check(request)
    conv = _conversation(request)
    history = list(conv.messages.all()) if conv else []
    context = {"history": history, "max_input": services.MAX_INPUT}
    if request.GET.get("teil") == "1":  # nur der Chat, für das Fenster auf allen Seiten
        return render(request, "assistant/_chat.html", context)
    return render(request, "assistant/chat.html", context)


@require_POST
@login_required
def send(request: HttpRequest) -> HttpResponse:
    """Frage stellen. Mit JavaScript (Header ``X-Uke``) kommt nur die Antwort als HTML-Schnipsel zurück."""
    _check(request)
    partial = request.headers.get("X-Uke") == "1"
    conv = _conversation(request)
    if conv is None:
        conv = Conversation.objects.create(user=request.user)  # type: ignore[misc]  # login_required
        request.session[SESSION_KEY] = conv.pk
    try:
        _, reply = services.ask(tools.Context(request), conv, request.POST.get("frage", ""))
    except services.AssistantError as error:
        if partial:
            return render(request, "assistant/_error.html", {"error": str(error)}, status=400)
        messages.error(request, str(error))
        return redirect("assistant")
    if partial:
        return render(request, "assistant/_message.html", {"message": reply})
    return redirect("assistant")


@require_POST
@login_required
def new(request: HttpRequest) -> HttpResponse:
    """Neues Gespräch: das alte verschwindet von der Seite (gespeichert bleibt es 30 Tage für die Auskunft)."""
    _check(request)
    request.session.pop(SESSION_KEY, None)
    if request.headers.get("X-Uke") == "1":
        return HttpResponse(status=204)
    return redirect("assistant")
