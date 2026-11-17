"""Hauptmenü an einer Stelle: Seitenleiste und Kacheln der Startseite zeigen dieselben Punkte, Gruppen und Icons.

Welche Punkte jemand sieht, steht in den Kontextvariablen der Apps (``can_join_team``, ``can_manage_members`` …).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.urls import reverse


@dataclass(frozen=True)
class Item:
    label: str
    icon: str  # Bootstrap Icon, z. B. „bi-house“
    url_name: str
    description: str = ""
    active: tuple[str, ...] = ()  # weitere URL-Namen, bei denen der Punkt aktiv ist
    tile: bool = True  # auch als Kachel auf der Startseite
    sidebar: bool = True

    @property
    def url(self) -> str:
        return reverse(self.url_name)

    def is_active(self, url_name: str | None) -> bool:
        return url_name is not None and (url_name == self.url_name or url_name in self.active)


@dataclass
class Group:
    title: str  # leer: ohne Überschrift
    items: list[Item] = field(default_factory=list)


def groups(context: Any) -> list[Group]:
    """Gruppen mit den Punkten, die der angemeldete Benutzer sehen darf; leere Gruppen fallen weg."""
    can = context.get
    own = Group(
        "",
        [
            Item("Start", "bi-house", "home", tile=False),
            Item(
                "Termine",
                "bi-calendar-week",
                "agenda",
                "Trainings und Veranstaltungen, An- und Abmelden",
                ("occurrence_detail", "register", "occurrence_edit", "participant_add"),
            ),
        ],
    )
    if can("has_own_members"):
        own.items.append(
            Item(
                "Meine Daten",
                "bi-person-vcard",
                "my_data",
                "Kontakt, Graduierung und Gewicht",
                ("my_member", "my_member_edit", "my_privacy"),
            )
        )
    if can("can_join_team"):
        decider = bool(can("can_decide_claims"))
        own.items.append(
            Item(
                "Meine Abrechnung",
                "bi-cash-coin",
                "billing_index",
                "Stunden bestätigen und Monate einreichen",
                ("billing_month",) if decider else ("billing_month", "claim_detail"),
            )
        )
    own.items.append(
        Item("Meine Anmeldung", "bi-person-circle", "security", "Passkeys, Passwort und Geräte", sidebar=False)
    )

    admin = Group("Verwaltung")
    if can("can_manage_members"):
        admin.items.append(
            Item(
                "Mitglieder",
                "bi-people",
                "member_list",
                "Mitglieder, Import und Zugänge",
                (
                    "member_detail",
                    "member_edit",
                    "member_create",
                    "member_import",
                    "interest_list",
                    "interest_edit",
                    "member_delete",
                ),
            )
        )
    if can("can_plan_events"):
        admin.items.append(
            Item(
                "Veranstaltungen",
                "bi-calendar3",
                "event_list",
                "Zeitpläne, Zielgruppen und Übungsleiter",
                (
                    "event_detail",
                    "event_edit",
                    "event_create",
                    "schedule_edit",
                    "schedule_create",
                    "occurrence_create",
                    "target_group_list",
                    "target_group_edit",
                    "target_group_create",
                    "target_group_members",
                    "role_list",
                    "role_edit",
                    "role_create",
                    "event_type_list",
                    "event_type_edit",
                    "event_type_create",
                ),
            )
        )
    if can("can_decide_claims"):
        admin.items.append(
            Item(
                "Abrechnungen",
                "bi-cash-coin",
                "claim_list",
                "Abrechnungen prüfen, Stundensätze pflegen",
                ("claim_detail", "rate_list", "rate_member"),
            )
        )
    if can("can_manage_users"):
        admin.items.append(
            Item(
                "Benutzer",
                "bi-person-badge",
                "user_list",
                "Zugänge einladen und Rollen vergeben",
                ("invite", "edit_user", "invitation_link"),
            )
        )
    if can("can_manage_members"):
        admin.items.append(Item("Protokoll", "bi-journal-text", "audit_list", "Wer wann was geändert hat"))

    tech = Group("Technik")
    user = can("user")
    if user is not None and getattr(user, "is_staff", False):
        tech.items += [
            Item("Bausteine", "bi-grid-1x2", "components", tile=False),
            Item("Technische Verwaltung", "bi-wrench-adjustable", "admin:index", tile=False),
        ]
    return [group for group in (own, admin, tech) if group.items]
