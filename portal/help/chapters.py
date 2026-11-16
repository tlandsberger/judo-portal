"""Kapitel der Hilfe (ADR 0016). Wer welches Kapitel sieht, folgt den Rechten aus den Fach-Apps."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from portal.accounts.permissions import can_manage_users
from portal.billing import services as billing
from portal.events import services as events
from portal.members import services as members


def _public(user: Any) -> bool:
    return True


def _signed_in(user: Any) -> bool:
    return bool(user.is_authenticated)


def _with_members(user: Any) -> bool:
    return bool(user.is_authenticated and members.effective_links(user))


def _team(user: Any) -> bool:
    return events.can_join_team(user)


def _manage_members(user: Any) -> bool:
    return members.can_manage_members(user)


def _manage_events(user: Any) -> bool:
    return events.can_manage_events(user)


def _billing(user: Any) -> bool:
    return billing.can_decide(user)


def _users(user: Any) -> bool:
    return bool(user.is_authenticated and can_manage_users(user))


@dataclass(frozen=True)
class Chapter:
    slug: str
    title: str
    icon: str
    group: str
    summary: str
    visible: Callable[[Any], bool]

    @property
    def template(self) -> str:
        return f"help/chapters/{self.slug}.html"


GROUPS = ("Für alle", "Termine", "Als Übungsleiter", "Verwaltung")

CHAPTERS = (
    Chapter(
        "erste-schritte",
        "Erste Schritte",
        "bi-rocket-takeoff",
        "Für alle",
        "Einladung annehmen, anmelden mit Passkey, Passwort oder Code, das Portal als App.",
        _public,
    ),
    Chapter(
        "benachrichtigungen",
        "Benachrichtigungen",
        "bi-bell",
        "Für alle",
        "Push-Benachrichtigungen einschalten, was per Mail kommt, wenn sie verspätet sind.",
        _signed_in,
    ),
    Chapter(
        "zugang",
        "Mein Zugang",
        "bi-person-circle",
        "Für alle",
        "Anmeldewege verwalten, Telefon für Notfälle, abmelden, Zugang löschen.",
        _signed_in,
    ),
    Chapter(
        "meine-daten",
        "Meine Daten und Datenschutz",
        "bi-shield-check",
        "Für alle",
        "Eigene Daten und die der Kinder ansehen und ändern, Datenauskunft, Löschfristen.",
        _signed_in,
    ),
    Chapter(
        "termine",
        "Termine und Anmeldung",
        "bi-calendar-week",
        "Termine",
        "Für dich oder deine Kinder anmelden, Warteliste, abmelden, Absagen.",
        _with_members,
    ),
    Chapter(
        "team",
        "Als Übungsleiter am Termin",
        "bi-people",
        "Als Übungsleiter",
        "Als Trainer oder Co-Trainer eintragen, Teilnehmerliste, Hinweis, Absage, Gäste.",
        _team,
    ),
    Chapter(
        "stunden",
        "Meine Stunden und Abrechnung",
        "bi-clipboard-check",
        "Als Übungsleiter",
        "Stunden bestätigen und korrigieren, Monat einreichen, Frist und Rückgabe.",
        _team,
    ),
    Chapter(
        "mitglieder",
        "Mitglieder verwalten",
        "bi-person-lines-fill",
        "Verwaltung",
        "Anlegen, CSV-Import, Zugänge für Mitglieder und Eltern, Austritt und Löschen.",
        _manage_members,
    ),
    Chapter(
        "veranstaltungen",
        "Veranstaltungen planen",
        "bi-calendar3",
        "Verwaltung",
        "Einmalig oder wiederkehrend anlegen, Zielgruppen, Übungsleiter, Rollen, Gäste, Absagen.",
        _manage_events,
    ),
    Chapter(
        "abrechnungen",
        "Abrechnungen prüfen",
        "bi-cash-coin",
        "Verwaltung",
        "Stundensätze, freigeben oder zurückgeben, PDF und CSV für die Geschäftsstelle.",
        _billing,
    ),
    Chapter(
        "benutzer",
        "Benutzer und Protokoll",
        "bi-people-fill",
        "Verwaltung",
        "Einladen, Rollen vergeben, deaktivieren; wer hat was geändert.",
        _users,
    ),
    Chapter(
        "fragen",
        "Fragen und Kontakt",
        "bi-question-circle",
        "Für alle",
        "Anmeldung klappt nicht, Mail kommt nicht an, Daten stimmen nicht.",
        _public,
    ),
)


def visible(user: Any) -> list[Chapter]:
    return [chapter for chapter in CHAPTERS if chapter.visible(user)]


def grouped(user: Any) -> list[tuple[str, list[Chapter]]]:
    chapters = visible(user)
    return [
        (group, [c for c in chapters if c.group == group])
        for group in GROUPS
        if any(c.group == group for c in chapters)
    ]


def get(slug: str, user: Any) -> Chapter | None:
    return next((chapter for chapter in visible(user) if chapter.slug == slug), None)
