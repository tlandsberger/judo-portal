"""Mitglieder (Vereinsdaten) und Verknüpfungen mit Benutzern (m:n, ADR 0003 und 0009)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

# Bis zu diesem Alter gilt eine Verknüpfung „Erziehungsberechtigt“; ab diesem Alter gibt es einen eigenen Zugang.
ADULT_AGE = 18
OWN_ACCESS_AGE = 14


class Gender(models.TextChoices):
    FEMALE = "w", "weiblich"
    MALE = "m", "männlich"
    DIVERSE = "d", "divers"


class Grade(models.TextChoices):
    """Graduierung nach Kyu/Dan (Gürtelfarben wie im Deutschen Judo-Bund), aufsteigend sortiert."""

    KYU_9 = "kyu9", "9. Kyu (weiß)"
    KYU_8 = "kyu8", "8. Kyu (weiß-gelb)"
    KYU_7 = "kyu7", "7. Kyu (gelb)"
    KYU_6 = "kyu6", "6. Kyu (gelb-orange)"
    KYU_5 = "kyu5", "5. Kyu (orange)"
    KYU_4 = "kyu4", "4. Kyu (orange-grün)"
    KYU_3 = "kyu3", "3. Kyu (grün)"
    KYU_2 = "kyu2", "2. Kyu (blau)"
    KYU_1 = "kyu1", "1. Kyu (braun)"
    DAN_1 = "dan1", "1. Dan (schwarz)"
    DAN_2 = "dan2", "2. Dan (schwarz)"
    DAN_3 = "dan3", "3. Dan (schwarz)"
    DAN_4 = "dan4", "4. Dan (schwarz)"
    DAN_5 = "dan5", "5. Dan (schwarz)"
    DAN_6 = "dan6", "6. Dan (rot-weiß)"
    DAN_7 = "dan7", "7. Dan (rot-weiß)"
    DAN_8 = "dan8", "8. Dan (rot-weiß)"
    DAN_9 = "dan9", "9. Dan (rot)"
    DAN_10 = "dan10", "10. Dan (rot)"

    @property
    def short_label(self) -> str:
        """Kurzform ohne Farbe, z. B. „5. Kyu“."""
        return str(self.label).split(" (")[0]


def grade_rank(grade: str) -> int:
    """Rang einer Graduierung zum Vergleichen: 0 = 9. Kyu, ohne Graduierung -1 (Anfänger)."""
    return Grade.values.index(grade) if grade in Grade.values else -1


class Interest(models.Model):
    """Was ein Mitglied im Judo interessiert (Wettkampf, Kata …). Die Liste pflegt die Abteilungsleitung."""

    name = models.CharField("Name", max_length=50, unique=True)
    position = models.PositiveSmallIntegerField("Reihenfolge", default=0)

    class Meta:
        verbose_name = "Interesse"
        verbose_name_plural = "Interessen"
        ordering = ("position", "name")

    def __str__(self) -> str:
        return self.name


class Member(models.Model):
    """Ein Vereinsmitglied. Bewusst sparsam: keine Adresse, keine Passnummer, Graduierung ohne Historie."""

    member_number = models.CharField(
        "Mitgliedsnummer",
        max_length=30,
        unique=True,
        null=True,
        blank=True,
        help_text="Nummer aus der Mitgliederverwaltung des Vereins; der CSV-Import gleicht darüber ab.",
    )
    first_name = models.CharField("Vorname", max_length=100)
    last_name = models.CharField("Nachname", max_length=100)
    birth_date = models.DateField("Geburtsdatum")
    gender = models.CharField("Geschlecht", max_length=1, choices=Gender.choices, blank=True)
    joined_on = models.DateField("Eintritt", null=True, blank=True)
    left_on = models.DateField("Austritt", null=True, blank=True)
    email = models.EmailField("E-Mail", blank=True)
    phone = models.CharField("Telefon", max_length=40, blank=True)
    grade = models.CharField("Graduierung", max_length=5, choices=Grade.choices, blank=True)
    weight = models.DecimalField(
        "Gewicht (kg)",
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("10")), MaxValueValidator(Decimal("250"))],
    )
    interests = models.ManyToManyField(Interest, verbose_name="Interessen", blank=True, related_name="members")
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Mitglied"
        verbose_name_plural = "Mitglieder"
        ordering = ("last_name", "first_name", "birth_date")

    def __str__(self) -> str:
        return self.display_name

    @property
    def display_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def age(self, on: date | None = None) -> int:
        on = on or timezone.localdate()
        born = self.birth_date
        return on.year - born.year - ((on.month, on.day) < (born.month, born.day))

    @property
    def is_active(self) -> bool:
        """Aktiv, solange kein Austrittsdatum erreicht ist."""
        return self.left_on is None or self.left_on > timezone.localdate()

    @property
    def grade_short(self) -> str:
        return Grade(self.grade).short_label if self.grade else ""


class LinkKind(models.TextChoices):
    SELF = "self", "Eigenes Profil"
    GUARDIAN = "guardian", "Erziehungsberechtigt"


class MemberLink(models.Model):
    """Verknüpfung Benutzer ↔ Mitglied. „Erziehungsberechtigt“ gilt nur bis zum 18. Geburtstag des Mitglieds."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="member_links")
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="links")
    kind = models.CharField("Art", max_length=10, choices=LinkKind.choices)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        verbose_name = "Verknüpfung"
        verbose_name_plural = "Verknüpfungen"
        constraints = [
            models.UniqueConstraint(fields=["user", "member"], name="member_link_unique"),
            # Ein Mitglied hat höchstens einen eigenen Zugang, ein Benutzer höchstens ein eigenes Profil.
            models.UniqueConstraint(
                fields=["member"], condition=models.Q(kind="self"), name="member_link_one_self_per_member"
            ),
            models.UniqueConstraint(
                fields=["user"], condition=models.Q(kind="self"), name="member_link_one_self_per_user"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} → {self.member} ({self.get_kind_display()})"

    def is_effective(self, on: date | None = None) -> bool:
        return self.kind == LinkKind.SELF or self.member.age(on) < ADULT_AGE


class PendingLink(models.Model):
    """Verknüpfung, die beim Annehmen einer Einladung angelegt wird."""

    invitation = models.ForeignKey("accounts.Invitation", on_delete=models.CASCADE, related_name="pending_links")
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="pending_links")
    kind = models.CharField("Art", max_length=10, choices=LinkKind.choices)

    class Meta:
        verbose_name = "Offene Verknüpfung"
        verbose_name_plural = "Offene Verknüpfungen"
        constraints = [models.UniqueConstraint(fields=["invitation", "member"], name="pending_link_unique")]

    def __str__(self) -> str:
        return f"{self.invitation.email} → {self.member} ({self.get_kind_display()})"
