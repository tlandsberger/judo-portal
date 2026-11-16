"""Übungsleiterabrechnung (ADR 0014): Stundensätze je Person und Rolle, Monatsabrechnungen mit Schnappschuss-Zeilen."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import formats, timezone

from portal.events.models import ParticipantRole, Participation
from portal.members.models import Member


class Rate(models.Model):
    """Stundensatz eines Übungsleiters für eine abrechnungsrelevante Rolle, gültig ab einem Tag."""

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="rates", verbose_name="Übungsleiter")
    role = models.ForeignKey(ParticipantRole, on_delete=models.PROTECT, related_name="rates", verbose_name="Rolle")
    hourly_rate = models.DecimalField(
        "Satz (€/Stunde)", max_digits=6, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )
    valid_from = models.DateField("Gültig ab")
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        verbose_name = "Stundensatz"
        verbose_name_plural = "Stundensätze"
        ordering = ("member", "role__order", "-valid_from")
        constraints = [models.UniqueConstraint(fields=("member", "role", "valid_from"), name="one_rate_per_day")]

    def __str__(self) -> str:
        return f"{self.member}: {self.role} {self.hourly_rate} € ab {self.valid_from:%d.%m.%Y}"


class ClaimStatus(models.TextChoices):
    SUBMITTED = "submitted", "eingereicht"
    RETURNED = "returned", "zurückgegeben"
    APPROVED = "approved", "freigegeben"


class Claim(models.Model):
    """Abrechnung eines Übungsleiters für einen Monat. Ein noch nicht eingereichter Monat hat keinen Datensatz."""

    member = models.ForeignKey(Member, on_delete=models.PROTECT, related_name="claims", verbose_name="Übungsleiter")
    month = models.DateField("Monat", help_text="Erster Tag des Monats.")
    status = models.CharField("Status", max_length=10, choices=ClaimStatus.choices, default=ClaimStatus.SUBMITTED)
    submitted_at = models.DateTimeField("Eingereicht am")
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+", verbose_name="Eingereicht von"
    )
    decided_at = models.DateTimeField("Entschieden am", null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Entschieden von",
    )
    decided_by_name = models.CharField("Entschieden von (Name)", max_length=200, blank=True)
    feedback = models.TextField("Rückmeldung", blank=True)
    total_minutes = models.PositiveIntegerField("Minuten", default=0)
    total_amount = models.DecimalField("Betrag (€)", max_digits=9, decimal_places=2, default=Decimal("0"))

    class Meta:
        verbose_name = "Abrechnung"
        verbose_name_plural = "Abrechnungen"
        ordering = ("-month", "member")
        constraints = [models.UniqueConstraint(fields=("member", "month"), name="one_claim_per_month")]

    def __str__(self) -> str:
        return f"{self.member} – {month_label(self.month)}"

    @property
    def month_label(self) -> str:
        return month_label(self.month)

    @property
    def hours(self) -> Decimal:
        return hours(self.total_minutes)

    @property
    def is_locked(self) -> bool:
        return self.status != ClaimStatus.RETURNED


class ClaimLine(models.Model):
    """Zeile der Abrechnung: Schnappschuss beim Einreichen; spätere Änderungen an Termin oder Rolle ändern nichts."""

    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name="lines")
    participation = models.OneToOneField(Participation, on_delete=models.PROTECT, related_name="claim_line")
    day = models.DateField("Datum")
    event_title = models.CharField("Veranstaltung", max_length=200)
    role_name = models.CharField("Rolle", max_length=60)
    minutes = models.PositiveIntegerField("Minuten")
    hourly_rate = models.DecimalField("Satz (€/Stunde)", max_digits=6, decimal_places=2)
    amount = models.DecimalField("Betrag (€)", max_digits=8, decimal_places=2)

    class Meta:
        verbose_name = "Abrechnungszeile"
        verbose_name_plural = "Abrechnungszeilen"
        ordering = ("day", "pk")

    def __str__(self) -> str:
        return f"{self.day:%d.%m.%Y} {self.event_title} ({self.role_name})"


def month_label(month: date) -> str:
    return formats.date_format(month, "F Y")


def hours(minutes: int) -> Decimal:
    return (Decimal(minutes) / 60).quantize(Decimal("0.01"))
