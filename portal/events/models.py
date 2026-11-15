"""Veranstaltungen, Termine, Anmeldungen und Begleitung durch Übungsleiter (ADR 0010)."""

from __future__ import annotations

from datetime import datetime, timedelta

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from portal.members.models import Gender, Grade, Interest, Member


class TargetGroup(models.Model):
    """Benannte Regel, an wen sich eine Veranstaltung richtet. Leere Kriterien gelten für alle."""

    name = models.CharField("Name", max_length=80, unique=True)
    description = models.CharField("Beschreibung", max_length=200, blank=True)
    min_age = models.PositiveSmallIntegerField(
        "Alter ab", null=True, blank=True, help_text="Nach Jahrgang: Jahr des Termins minus Geburtsjahr."
    )
    max_age = models.PositiveSmallIntegerField("Alter bis", null=True, blank=True)
    genders = models.JSONField("Geschlecht", default=list, blank=True, help_text="Leer heißt: alle.")
    min_weight = models.DecimalField(
        "Gewicht ab (kg)", max_digits=4, decimal_places=1, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    max_weight = models.DecimalField(
        "Gewicht bis (kg)", max_digits=4, decimal_places=1, null=True, blank=True, validators=[MaxValueValidator(250)]
    )
    min_grade = models.CharField("Graduierung ab", max_length=5, choices=Grade.choices, blank=True)
    max_grade = models.CharField("Graduierung bis", max_length=5, choices=Grade.choices, blank=True)
    interests = models.ManyToManyField(
        Interest, verbose_name="Interessen", blank=True, help_text="Passt, wenn das Mitglied eines davon gewählt hat."
    )

    class Meta:
        verbose_name = "Zielgruppe"
        verbose_name_plural = "Zielgruppen"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name

    def get_genders_display(self) -> str:
        return ", ".join(str(Gender(g).label) for g in self.genders)

    @property
    def summary(self) -> str:
        """Kriterien in einer Zeile, z. B. „Alter 10–12 · männlich · ab 5. Kyu“."""
        parts = []
        if self.min_age is not None or self.max_age is not None:
            parts.append(_range("Alter", self.min_age, self.max_age))
        if self.genders:
            parts.append(self.get_genders_display())
        if self.min_weight is not None or self.max_weight is not None:
            parts.append(_range("", self.min_weight, self.max_weight, " kg").strip())
        if self.min_grade or self.max_grade:
            low = f"ab {Grade(self.min_grade).short_label}" if self.min_grade else ""
            high = f"bis {Grade(self.max_grade).short_label}" if self.max_grade else ""
            parts.append(f"{low} {high}".strip())
        if self.pk and (names := [interest.name for interest in self.interests.all()]):
            parts.append(" oder ".join(names))
        return " · ".join(parts) or "alle Mitglieder"


def _range(label: str, low: object, high: object, unit: str = "") -> str:
    def fmt(value: object) -> str:
        return str(value).replace(".", ",")

    if low is not None and high is not None:
        return f"{label} {fmt(low)}–{fmt(high)}{unit}"
    if low is not None:
        return f"{label} ab {fmt(low)}{unit}"
    return f"{label} bis {fmt(high)}{unit}"


class EventKind(models.TextChoices):
    TRAINING = "training", "Training"
    COMPETITION = "competition", "Wettkampf"
    COURSE = "course", "Lehrgang"
    EXAM = "exam", "Prüfung"
    OTHER = "other", "Sonstiges"


class Event(models.Model):
    """Das „Was“: Training, Wettkampf … Termine entstehen aus Zeitplänen oder werden von Hand ergänzt."""

    title = models.CharField("Titel", max_length=120)
    kind = models.CharField("Art", max_length=12, choices=EventKind.choices, default=EventKind.TRAINING)
    description = models.TextField("Beschreibung", blank=True)
    location = models.CharField("Ort", max_length=120, blank=True)
    target_groups = models.ManyToManyField(
        TargetGroup,
        verbose_name="Zielgruppen",
        blank=True,
        related_name="events",
        help_text="Anmelden kann sich, wer zu mindestens einer passt. Ohne Zielgruppe: alle.",
    )
    capacity = models.PositiveSmallIntegerField(
        "Höchstzahl je Termin",
        null=True,
        blank=True,
        help_text="Leer heißt: unbegrenzt. Sonst gibt es eine Warteliste.",
    )
    weight_required = models.BooleanField(
        "Gewicht bei Anmeldung erforderlich", default=False, help_text="Zum Beispiel für Wettkämpfe."
    )
    registration_opens_at = models.DateTimeField("Anmeldung ab", null=True, blank=True)
    registration_closes_at = models.DateTimeField("Anmeldeschluss", null=True, blank=True)
    opens_days_before = models.PositiveSmallIntegerField(
        "Anmeldung öffnet (Tage vorher)", null=True, blank=True, help_text="Für wiederkehrende Termine."
    )
    closes_hours_before = models.PositiveSmallIntegerField(
        "Anmeldung schließt (Stunden vorher)", null=True, blank=True, help_text="Für wiederkehrende Termine."
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        verbose_name = "Veranstaltung"
        verbose_name_plural = "Veranstaltungen"
        ordering = ("title",)

    def __str__(self) -> str:
        return self.title


class Weekday(models.IntegerChoices):
    MONDAY = 0, "Montag"
    TUESDAY = 1, "Dienstag"
    WEDNESDAY = 2, "Mittwoch"
    THURSDAY = 3, "Donnerstag"
    FRIDAY = 4, "Freitag"
    SATURDAY = 5, "Samstag"
    SUNDAY = 6, "Sonntag"


class Schedule(models.Model):
    """Zeitplan einer wiederkehrenden Veranstaltung, z. B. „Dienstag 17:00–18:30“ für einen Zeitraum."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="schedules")
    weekday = models.PositiveSmallIntegerField("Wochentag", choices=Weekday.choices)
    start_time = models.TimeField("Beginn")
    end_time = models.TimeField("Ende")
    valid_from = models.DateField("Gültig ab")
    valid_until = models.DateField("Gültig bis", null=True, blank=True, help_text="Leer heißt: bis auf Weiteres.")
    generated_until = models.DateField(null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "Zeitplan"
        verbose_name_plural = "Zeitpläne"
        ordering = ("valid_from", "weekday", "start_time")

    def __str__(self) -> str:
        return f"{self.get_weekday_display()} {self.start_time:%H:%M}–{self.end_time:%H:%M}"


class Occurrence(models.Model):
    """Ein Termin. Aus einem Zeitplan erzeugt oder von Hand angelegt (Zusatztermin, einmalige Veranstaltung)."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="occurrences")
    schedule = models.ForeignKey(Schedule, on_delete=models.SET_NULL, null=True, blank=True, related_name="occurrences")
    starts_at = models.DateTimeField("Beginn")
    ends_at = models.DateTimeField("Ende")
    location = models.CharField("Abweichender Ort", max_length=120, blank=True)
    note = models.CharField("Hinweis", max_length=300, blank=True)
    is_modified = models.BooleanField(default=False, editable=False)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Termin"
        verbose_name_plural = "Termine"
        ordering = ("starts_at",)

    def __str__(self) -> str:
        return f"{self.event} am {timezone.localtime(self.starts_at):%d.%m.%Y %H:%M}"

    @property
    def is_cancelled(self) -> bool:
        return self.cancelled_at is not None

    @property
    def place(self) -> str:
        return self.location or self.event.location

    @property
    def minutes(self) -> int:
        return int((self.ends_at - self.starts_at).total_seconds() // 60)

    @property
    def registration_opens(self) -> datetime | None:
        event = self.event
        if event.registration_opens_at:
            return event.registration_opens_at
        if event.opens_days_before is not None:
            return self.starts_at - timedelta(days=event.opens_days_before)
        return None

    @property
    def registration_closes(self) -> datetime:
        event = self.event
        if event.registration_closes_at:
            return event.registration_closes_at
        if event.closes_hours_before is not None:
            return self.starts_at - timedelta(hours=event.closes_hours_before)
        return self.starts_at


class RegistrationStatus(models.TextChoices):
    REGISTERED = "registered", "Angemeldet"
    WAITLIST = "waitlist", "Warteliste"
    CANCELLED = "cancelled", "Abgemeldet"


class Registration(models.Model):
    """Teilnahme eines Mitglieds an einem Termin."""

    occurrence = models.ForeignKey(Occurrence, on_delete=models.CASCADE, related_name="registrations")
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="registrations")
    status = models.CharField("Status", max_length=10, choices=RegistrationStatus.choices)
    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    exception_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="Ausnahme: angemeldet, obwohl das Mitglied nicht zur Zielgruppe passt.",
    )
    weight = models.DecimalField("Gewicht (kg)", max_digits=4, decimal_places=1, null=True, blank=True)
    note = models.CharField("Hinweis", max_length=200, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Anmeldung"
        verbose_name_plural = "Anmeldungen"
        ordering = ("created_at",)
        constraints = [models.UniqueConstraint(fields=["occurrence", "member"], name="registration_unique")]

    def __str__(self) -> str:
        return f"{self.member} – {self.occurrence} ({self.get_status_display()})"

    @property
    def is_active(self) -> bool:
        return self.status != RegistrationStatus.CANCELLED


class StaffFunction(models.TextChoices):
    TRAINER = "trainer", "Trainer"
    CO_TRAINER = "co_trainer", "Kotrainer"


class EventStaff(models.Model):
    """Standard-Team einer Veranstaltung; neue Termine übernehmen es."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="staff")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="event_staff")
    function = models.CharField("Funktion", max_length=10, choices=StaffFunction.choices)

    class Meta:
        verbose_name = "Standard-Team"
        verbose_name_plural = "Standard-Team"
        ordering = ("function", "user__first_name")
        constraints = [models.UniqueConstraint(fields=["event", "user"], name="event_staff_unique")]

    def __str__(self) -> str:
        return f"{self.user} – {self.event} ({self.get_function_display()})"


class Staffing(models.Model):
    """Begleitung eines Termins durch einen Übungsleiter. Grundlage der späteren Übungsleiterabrechnung."""

    occurrence = models.ForeignKey(Occurrence, on_delete=models.CASCADE, related_name="staffings")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staffings")
    function = models.CharField("Funktion", max_length=10, choices=StaffFunction.choices)
    confirmed_at = models.DateTimeField("Bestätigt am", null=True, blank=True)
    minutes = models.PositiveIntegerField("Dauer (Minuten)", null=True, blank=True)

    class Meta:
        verbose_name = "Begleitung"
        verbose_name_plural = "Begleitungen"
        ordering = ("function", "user__first_name")
        constraints = [models.UniqueConstraint(fields=["occurrence", "user"], name="staffing_unique")]

    def __str__(self) -> str:
        return f"{self.user} – {self.occurrence} ({self.get_function_display()})"

    @property
    def is_confirmed(self) -> bool:
        return self.confirmed_at is not None
