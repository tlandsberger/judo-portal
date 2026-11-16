from __future__ import annotations

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render

from . import chapters


def index(request: HttpRequest) -> HttpResponse:
    return render(request, "help/index.html", {"groups": chapters.grouped(request.user)})


def chapter(request: HttpRequest, slug: str) -> HttpResponse:
    current = chapters.get(slug, request.user)
    if current is None:
        raise Http404
    visible = chapters.visible(request.user)
    position = visible.index(current)
    return render(
        request,
        "help/chapter.html",
        {
            "chapter": current,
            "previous": visible[position - 1] if position > 0 else None,
            "next": visible[position + 1] if position + 1 < len(visible) else None,
        },
    )
