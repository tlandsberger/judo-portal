"""Geräte für Push-Benachrichtigungen und Protokoll versendeter Benachrichtigungen (ADR 0011)."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class PushNotificationSubscription(models.Model):
    """Ein Gerät (Browser), auf dem der Benutzer Push-Benachrichtigungen eingeschaltet hat."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="push_notification_subscriptions"
    )
    endpoint = models.URLField("Endpoint", max_length=1000, unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    device = models.CharField("Gerät", max_length=100, blank=True)
    created_at = models.DateTimeField("Eingerichtet am", default=timezone.now)
    last_used_at = models.DateTimeField("Zuletzt genutzt", null=True, blank=True)

    class Meta:
        verbose_name = "Gerät für Push-Benachrichtigungen"
        verbose_name_plural = "Geräte für Push-Benachrichtigungen"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.user} – {self.device or 'Gerät'}"

    def as_subscription_info(self) -> dict[str, object]:
        return {"endpoint": self.endpoint, "keys": {"p256dh": self.p256dh, "auth": self.auth}}


class Channel(models.TextChoices):
    PENDING = "pending", "Wird verschickt"
    PUSH_NOTIFICATION = "push", "Push-Benachrichtigung"
    MAIL = "mail", "E-Mail"


class SentNotification(models.Model):
    """Jede Benachrichtigung geht je Schlüssel nur einmal raus (z. B. ``registration_open:<termin>:<benutzer>``)."""

    key = models.CharField(max_length=200, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    kind = models.CharField("Anlass", max_length=40)
    title = models.CharField("Titel", max_length=120)
    channel = models.CharField("Kanal", max_length=10, choices=Channel.choices, default=Channel.PENDING)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Versandte Benachrichtigung"
        verbose_name_plural = "Versandte Benachrichtigungen"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.kind} an {self.user} ({self.get_channel_display()})"
