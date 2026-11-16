"""Änderungsprotokoll (ADR 0015). In ``portal.core``, damit jede App protokollieren kann, ohne andere zu kennen."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class Area(models.TextChoices):
    MEMBERS = "members", "Mitglieder"
    USERS = "users", "Benutzer"
    LOGIN = "login", "Anmeldung und Einstellungen"
    EVENTS = "events", "Termine"
    BILLING = "billing", "Abrechnung"
    PRIVACY = "privacy", "Datenschutz"


class AuditEntry(models.Model):
    """Wer hat wann was geändert. Bezüge als einfache IDs, damit ``core`` die Fach-Apps nicht kennt."""

    at = models.DateTimeField("Zeitpunkt", default=timezone.now, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Von",
    )
    actor_name = models.CharField("Von (Name)", max_length=200, blank=True)
    area = models.CharField("Bereich", max_length=20, choices=Area.choices)
    action = models.CharField("Aktion", max_length=40)
    summary = models.CharField("Beschreibung", max_length=300)
    member_id = models.PositiveIntegerField("Mitglied", null=True, blank=True, db_index=True)
    user_id = models.PositiveIntegerField("Benutzer", null=True, blank=True, db_index=True)
    guest_id = models.PositiveIntegerField("Gast", null=True, blank=True, db_index=True)
    changes = models.JSONField("Änderungen", default=dict, blank=True)

    class Meta:
        verbose_name = "Protokolleintrag"
        verbose_name_plural = "Protokoll"
        ordering = ("-at", "-pk")

    def __str__(self) -> str:
        return f"{self.at:%d.%m.%Y %H:%M} {self.actor_name or 'automatisch'}: {self.summary}"

    @property
    def who(self) -> str:
        return self.actor_name or "automatisch"
