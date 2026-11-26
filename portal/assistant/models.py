"""Gespräche mit dem Assistenten Uke (ADR 0028). Sie bleiben 30 Tage für die Auskunft und werden dann gelöscht;
im Portal zeigt nur die Chat-Seite das laufende Gespräch."""

from __future__ import annotations

from django.conf import settings
from django.db import models


class Conversation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assistant_conversations")
    started_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Gespräch mit Uke"
        verbose_name_plural = "Gespräche mit Uke"
        ordering = ("-started_at",)

    def __str__(self) -> str:
        return f"Gespräch {self.pk}"


class MessageRole(models.TextChoices):
    USER = "user", "Du"
    ASSISTANT = "assistant", "Uke"


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=MessageRole.choices)
    content = models.TextField()
    # Links zu den Seiten, die die Werkzeuge gefunden haben: [{"ref": "T12", "label": …, "url": …, "inline": True}];
    # „inline“: der Text nennt den Termin mit seiner Marke [T12] und zeigt ihn dort als Link
    links = models.JSONField(default=list, blank=True)
    # Namen der Werkzeuge, die Uke für diese Antwort benutzt hat (für die Auskunft)
    tools = models.JSONField(default=list, blank=True)
    failed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Nachricht"
        verbose_name_plural = "Nachrichten"
        ordering = ("created_at", "pk")

    def __str__(self) -> str:
        return f"{self.get_role_display()}: {self.content[:40]}"

    @property
    def extra_links(self) -> list[dict[str, str]]:
        """Links unter der Antwort: gefundene Seiten, die der Text nicht selbst als Link nennt."""
        return [link for link in self.links if not link.get("inline")]

    @property
    def is_user(self) -> bool:
        return self.role == MessageRole.USER
