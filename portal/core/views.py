from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.cache import cache_control, never_cache

from portal.accounts.models import Role
from portal.accounts.permissions import role_required


@login_required
def home(request: HttpRequest) -> HttpResponse:
    return render(request, "core/home.html")


@role_required(Role.ADMIN)
def components(request: HttpRequest) -> HttpResponse:
    """Bausteine des Designs als visuelle Referenz (auch für die Screenshot-Tests)."""
    tiles = [
        ("verein-mitglieder", "Mitglieder", "Stammdaten und Zugänge"),
        ("judo-termine", "Termine", "Trainings und Veranstaltungen"),
        ("judo-training", "Training", "Gruppen und Anwesenheit"),
        ("verein-finanzen", "Abrechnung", "Übungsleiterstunden"),
    ]
    return render(request, "core/components.html", {"tiles": tiles})


@never_cache
def healthz(request: HttpRequest) -> HttpResponse:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return HttpResponse("ok", content_type="text/plain")


@cache_control(max_age=3600)
def manifest(request: HttpRequest) -> HttpResponse:
    return render(request, "core/manifest.webmanifest", content_type="application/manifest+json")


@cache_control(no_cache=True)
def service_worker(request: HttpRequest) -> HttpResponse:
    # Am Wurzelpfad ausgeliefert, damit der Service Worker die ganze Seite abdeckt.
    response = render(request, "core/sw.js", content_type="text/javascript")
    response["Service-Worker-Allowed"] = "/"
    return response


def offline(request: HttpRequest) -> HttpResponse:
    return render(request, "core/offline.html")
