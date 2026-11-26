"""Werkzeuge, die Uke benutzen darf (ADR 0028).

Jedes Werkzeug ruft nur Services der Fach-Apps auf, mit dem angemeldeten Benutzer – so sieht Uke genau das, was der
Benutzer auch auf den Seiten sieht, und nie mehr. Das Modell bekommt nur das Ergebnis als JSON; Werkzeuge, die der
Benutzer nicht nutzen darf, werden ihm gar nicht erst angeboten. Werkzeuge, die etwas ändern, gibt es hier noch nicht:
Sie dürfen später nur einen Vorschlag erzeugen, den der Benutzer bestätigt.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from html import unescape
from typing import Any

from django.http import HttpRequest
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags

from portal.events import services as events
from portal.events.models import Occurrence

WEEKDAYS = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")
MAX_DAYS = 62  # längster Zeitraum für eine Suche
DEFAULT_DAYS = 14
NAMES_UP_TO = 3  # bis zu so vielen Treffern stehen die Teilnehmer gleich dabei
MAX_RESULTS = 20
MAX_LINKS = 6
MATCH_LABELS = {events.Match.YES: "ja", events.Match.MAYBE: "vielleicht (Gewicht fehlt)", events.Match.NO: "nein"}
WINDOW_LABELS = {"before": "noch nicht offen", "open": "offen", "closed": "geschlossen"}


@dataclass
class Context:
    """Wer fragt: der angemeldete Benutzer (für alle Rechteprüfungen) und die Anfrage (für Hilfe-Texte)."""

    request: HttpRequest

    @property
    def user(self) -> Any:
        return self.request.user


@dataclass
class Result:
    data: Any
    links: list[dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    run: Callable[[Context, dict[str, Any]], Result]
    available: Callable[[Any], bool] = lambda user: True

    @property
    def spec(self) -> dict[str, Any]:
        """Beschreibung für das Modell im OpenAI-Format."""
        return {
            "type": "function",
            "function": {"name": self.name, "description": self.description, "parameters": self.parameters},
        }


class ToolError(Exception):
    """Falsche Angaben vom Modell; die Nachricht geht an das Modell zurück, damit es sich korrigiert."""


def _when(occurrence: Occurrence) -> str:
    start = timezone.localtime(occurrence.starts_at)
    end = timezone.localtime(occurrence.ends_at)
    return f"{WEEKDAYS[start.weekday()]}, {start:%d.%m.%Y}, {start:%H:%M}–{end:%H:%M} Uhr"


def _link(occurrence: Occurrence) -> dict[str, str]:
    start = timezone.localtime(occurrence.starts_at)
    return {
        "label": f"{occurrence.event.title}, {WEEKDAYS[start.weekday()]} {start:%d.%m. %H:%M}",
        "url": reverse("occurrence_detail", args=[occurrence.pk]),
    }


def _date(value: Any, name: str) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError as error:
        raise ToolError(f"{name} muss ein Datum im Format JJJJ-MM-TT sein.") from error


def _team(occurrence: Occurrence) -> list[str]:
    return [f"{p.member} ({p.role.name})" for p in occurrence.participations.all() if p.role.is_team and p.is_active]


# Termine suchen


def search_occurrences(ctx: Context, args: dict[str, Any]) -> Result:
    today = timezone.localdate()
    start = _date(args.get("von"), "von") or today
    hint = ""
    if start < today:
        start, hint = today, "Vergangene Termine kann Uke noch nicht nachsehen, die Suche beginnt heute."
    end = _date(args.get("bis"), "bis") or start + timedelta(days=DEFAULT_DAYS)
    end = min(max(end, start), start + timedelta(days=MAX_DAYS))
    text = str(args.get("suche") or "").strip().lower()
    flt = events.AgendaFilter(matching=False, mine=bool(args.get("nur_angemeldet")), end=end)
    found = []
    for entry in events.agenda(ctx.user, flt).entries:
        occurrence = entry.occurrence
        if timezone.localdate(occurrence.starts_at) < start:
            continue
        haystack = f"{occurrence.event.title} {occurrence.event.event_type} {occurrence.place}".lower()
        if text and text not in haystack:
            continue
        found.append(entry)
    try:
        limit = max(1, min(int(args.get("anzahl") or MAX_RESULTS), MAX_RESULTS))
    except (TypeError, ValueError) as error:
        raise ToolError("anzahl muss eine Zahl sein.") from error
    total = len(found)
    found = found[:limit]
    names = len(found) <= NAMES_UP_TO
    data: dict[str, Any] = {
        "zeitraum": f"{start:%d.%m.%Y} bis {end:%d.%m.%Y}",
        "anzahl": total,
        "termine": [
            _participants(ctx, entry.occurrence, names)
            | {
                "termin_id": entry.occurrence.pk,
                "titel": entry.occurrence.event.title,
                "art": str(entry.occurrence.event.event_type),
                "wann": _when(entry.occurrence),
                "ort": entry.occurrence.place,
                "abgesagt": entry.occurrence.is_cancelled,
                "hinweis": entry.occurrence.note,
                "anmeldung": WINDOW_LABELS[events.window(entry.occurrence)],
                "uebungsleiter": _team(entry.occurrence),
                "eigene_mitglieder": [
                    {
                        "mitglied": str(row.member),
                        "passt_zur_zielgruppe": MATCH_LABELS[row.item.match],
                        "status": _status(row.item),
                    }
                    for row in entry.rows
                ],
            }
            for entry in found
        ],
    }
    if total > len(found) == MAX_RESULTS:
        data["hinweis"] = f"Nur die ersten {MAX_RESULTS} Termine; für mehr den Zeitraum verkleinern."
    if hint:
        data["hinweis_zeitraum"] = hint
    links = [_link(entry.occurrence) for entry in found] if len(found) <= MAX_LINKS else []
    return Result(data, links)


def _participants(ctx: Context, occurrence: Occurrence, with_names: bool) -> dict[str, Any]:
    """Wer die Teilnehmerliste sehen darf, bekommt die Anzahl und bei wenigen Treffern gleich die Namen – kleine
    Modelle rufen termin_details sonst oft nicht nach."""
    if not events.can_see_participants(ctx.user, occurrence):
        return {}
    data: dict[str, Any] = {"angemeldet": events.registered_count(occurrence)}
    if with_names:
        data["teilnehmer"] = [
            f"{row.person} ({row.participation.get_status_display()})" for row in events.participants(occurrence)
        ]
    else:
        data["teilnehmerliste"] = "Namen mit termin_details abrufen"
    return data


def _status(item: events.AgendaItem) -> str:
    if item.team_role:
        return f"eingeteilt als {item.team_role.name}"
    if item.participation and item.participation.is_active:
        return item.participation.get_status_display()
    if item.participation:
        return "abgemeldet"
    if item.blocked:
        return "nicht angemeldet; passt nicht zur Zielgruppe, anmelden nur durch Übungs- oder Abteilungsleiter"
    return "nicht angemeldet"


# Ein Termin im Detail


def occurrence_details(ctx: Context, args: dict[str, Any]) -> Result:
    try:
        pk = int(args.get("termin_id"))  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise ToolError("termin_id fehlt; erst mit termine_suchen die ID herausfinden.") from error
    occurrence = Occurrence.objects.select_related("event__event_type").filter(pk=pk).first()
    if occurrence is None:
        raise ToolError(f"Einen Termin mit der ID {pk} gibt es nicht.")
    event = occurrence.event
    capacity = event.capacity
    data: dict[str, Any] = {
        "termin_id": occurrence.pk,
        "titel": event.title,
        "art": str(event.event_type),
        "wann": _when(occurrence),
        "ort": occurrence.place,
        "beschreibung": event.description[:800],
        "hinweis": occurrence.note,
        "abgesagt": occurrence.is_cancelled,
        "anmeldung": WINDOW_LABELS[events.window(occurrence)],
        "zielgruppen": [str(group) for group in events.target_groups(occurrence)] or ["alle Mitglieder"],
        "zielgruppen_sind": "Empfehlung" if events.is_recommendation(occurrence) else "Vorgabe",
        "angemeldet": events.registered_count(occurrence),
        "hoechstzahl": capacity if capacity is not None else "unbegrenzt",
        "uebungsleiter": [f"{p.member} ({p.role.name})" for p in events.team(occurrence)],
    }
    if events.can_see_participants(ctx.user, occurrence):
        data["teilnehmer"] = [
            {"name": str(row.person), "status": row.participation.get_status_display()}
            for row in events.participants(occurrence)
        ]
    return Result(data, [_link(occurrence)])


# Hilfe


_WORD = re.compile(r"\w{3,}")


def _chapter_text(ctx: Context, template: str) -> str:
    html = render_to_string(template, {"user": ctx.user}, request=ctx.request)
    return re.sub(r"\s+", " ", unescape(strip_tags(html))).strip()


def search_help(ctx: Context, args: dict[str, Any]) -> Result:
    from portal.help.chapters import CHAPTERS  # erst hier: die Hilfe kennt Uke für ihr eigenes Kapitel

    words = {word.lower() for word in _WORD.findall(str(args.get("frage") or ""))}
    if not words:
        raise ToolError("frage fehlt.")
    scored = []
    for chapter in CHAPTERS:
        if not chapter.visible(ctx.user):
            continue
        text = _chapter_text(ctx, chapter.template)
        # Absätze grob nach Sätzen bündeln und nach Treffern der Suchwörter bewerten
        sentences = re.split(r"(?<=[.!?])\s+", text)
        for index in range(0, len(sentences), 4):
            part = " ".join(sentences[index : index + 4])
            lower = part.lower()
            score = sum(lower.count(word) for word in words)
            if score:
                scored.append((score, chapter, part[:700]))
    scored.sort(key=lambda row: -row[0])
    best = scored[:3]
    data = [{"kapitel": chapter.title, "text": part} for _, chapter, part in best]
    links = []
    for _, chapter, _ in best:
        link = {"label": f"Hilfe: {chapter.title}", "url": reverse("help_chapter", args=[chapter.slug])}
        if link not in links:
            links.append(link)
    return Result(data or {"hinweis": "Nichts in der Hilfe gefunden."}, links)


TOOLS = (
    Tool(
        "termine_suchen",
        "Sucht Termine (Trainings, Wettkämpfe, Lehrgänge) in einem Zeitraum. Liefert je Termin die termin_id, "
        "Zeit, Ort, Übungsleiter, Anmeldestatus und für die eigenen Mitglieder des Benutzers, ob sie angemeldet sind. "
        "Die Termine sind nach Beginn sortiert, der erste ist der nächste. Für „bald“ einen längeren Zeitraum "
        "wählen (bis 60 Tage).",
        {
            "type": "object",
            "properties": {
                "von": {"type": "string", "description": "Erster Tag, JJJJ-MM-TT. Standard: heute."},
                "bis": {"type": "string", "description": "Letzter Tag, JJJJ-MM-TT. Standard: zwei Wochen nach von."},
                "suche": {"type": "string", "description": "Optional: Teil des Titels, der Art oder des Orts."},
                "anzahl": {
                    "type": "integer",
                    "description": "Nur die ersten so vielen Termine, z. B. 1 für „der nächste“. Bei höchstens 3 "
                    "Terminen stehen die Teilnehmer dabei, wenn der Benutzer sie sehen darf.",
                },
                "nur_angemeldet": {
                    "type": "boolean",
                    "description": "Nur Termine, zu denen ein eigenes Mitglied angemeldet oder eingeteilt ist.",
                },
            },
        },
        search_occurrences,
    ),
    Tool(
        "termin_details",
        "Details zu einem Termin: Beschreibung, Zielgruppen, Anzahl Anmeldungen, Übungsleiter und die "
        "Teilnehmerliste (nur wenn der Benutzer sie sehen darf). Für „Wer ist angemeldet?“ diese Funktion nutzen.",
        {
            "type": "object",
            "properties": {"termin_id": {"type": "integer", "description": "ID aus termine_suchen."}},
            "required": ["termin_id"],
        },
        occurrence_details,
    ),
    Tool(
        "hilfe_suchen",
        "Sucht in der Hilfe des Portals, wie etwas funktioniert (z. B. Passkey einrichten, Stunden bestätigen).",
        {
            "type": "object",
            "properties": {"frage": {"type": "string", "description": "Stichworte oder die Frage."}},
            "required": ["frage"],
        },
        search_help,
    ),
)


def available(user: Any) -> list[Tool]:
    return [tool for tool in TOOLS if tool.available(user)]
