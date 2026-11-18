"""Veranstaltungen, Termine und Teilnahme mit Rollen (Teilnehmer, Trainer, Co-Trainer …), ADR 0010 und 0012."""

from __future__ import annotations

import secrets
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from portal.core import ordering
from portal.members.models import Gender, Grade, Interest, Member


class Criteria(models.Model):
    """Kriterien einer Zielgruppe. Leere Kriterien gelten für alle; innerhalb gilt UND."""

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

    CRITERIA = ("min_age", "max_age", "genders", "min_weight", "max_weight", "min_grade", "max_grade")

    class Meta:
        abstract = True

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


class TargetGroupTemplate(Criteria):
    """Vorlage für Zielgruppen. Beim Übernehmen wird sie in die Veranstaltung kopiert (ADR 0010)."""

    name = models.CharField("Name", max_length=80, unique=True)
    description = models.CharField("Beschreibung", max_length=200, blank=True)

    class Meta:
        verbose_name = "Zielgruppen-Vorlage"
        verbose_name_plural = "Zielgruppen-Vorlagen"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name

    def apply_to(self, event: Event) -> TargetGroup:
        group = TargetGroup.objects.create(
            event=event, name=self.name, **{name: getattr(self, name) for name in self.CRITERIA}
        )
        group.interests.set(self.interests.all())
        return group


def _range(label: str, low: object, high: object, unit: str = "") -> str:
    def fmt(value: object) -> str:
        return str(value).replace(".", ",")

    if low is not None and high is not None:
        return f"{label} {fmt(low)}–{fmt(high)}{unit}"
    if low is not None:
        return f"{label} ab {fmt(low)}{unit}"
    return f"{label} bis {fmt(high)}{unit}"


class EventType(models.Model):
    """Veranstaltungsart (Training, Wettkampf …), pflegt die Abteilungsleitung."""

    name = models.CharField("Name", max_length=60, unique=True)
    order = models.PositiveSmallIntegerField("Reihenfolge", default=0)
    is_active = models.BooleanField("Aktiv", default=True, help_text="Inaktive Arten stehen nicht mehr zur Auswahl.")

    class Meta:
        verbose_name = "Veranstaltungsart"
        verbose_name_plural = "Veranstaltungsarten"
        ordering = ("order", "name")

    def __str__(self) -> str:
        return self.name

    def save(self, *args: Any, **kwargs: Any) -> None:
        ordering.append(self, "order")
        super().save(*args, **kwargs)


def default_event_type() -> int | None:
    first = EventType.objects.filter(is_active=True).order_by("order", "name").first()
    return first.pk if first else None


class TargetMode(models.TextChoices):
    REQUIRED = "required", "Vorgabe"
    RECOMMENDED = "recommended", "Empfehlung"


class Event(models.Model):
    """Das „Was“: Training, Wettkampf … Termine entstehen aus Zeitplänen oder werden von Hand ergänzt."""

    title = models.CharField("Titel", max_length=120)
    event_type = models.ForeignKey(
        EventType, on_delete=models.PROTECT, related_name="events", verbose_name="Art", default=default_event_type
    )
    description = models.TextField("Beschreibung", blank=True)
    location = models.CharField("Ort", max_length=120, blank=True)
    capacity = models.PositiveSmallIntegerField(
        "Höchstzahl je Termin",
        null=True,
        blank=True,
        help_text="Leer heißt: unbegrenzt. Sonst gibt es eine Warteliste.",
    )
    weight_required = models.BooleanField(
        "Gewicht bei Anmeldung erforderlich", default=False, help_text="Zum Beispiel für Wettkämpfe."
    )
    guests_welcome = models.BooleanField(
        "Externe Teilnehmer zulassen",
        default=False,
        help_text="Externe Teilnehmer ohne Zugang melden sich über einen Link an oder werden von den Übungsleitern "
        "eingetragen.",
    )
    guest_token = models.CharField(max_length=40, blank=True, editable=False)
    target_mode = models.CharField(
        "Zielgruppen gelten als",
        max_length=12,
        choices=TargetMode.choices,
        default=TargetMode.REQUIRED,
        help_text="Vorgabe: Wer nicht passt, kann nur von den Übungsleitern oder der Abteilungsleitung angemeldet "
        "werden. Empfehlung: Jeder kann sich anmelden; die Übungsleiter erfahren, wenn jemand nicht passt.",
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        verbose_name = "Veranstaltung"
        verbose_name_plural = "Veranstaltungen"
        ordering = ("title",)

    def __str__(self) -> str:
        return self.title


def attachment_path(instance: EventAttachment, filename: str) -> str:
    """Ablage unter anhaenge/<Veranstaltung>/ mit zufälligem Namen; der Originalname steht in ``filename``."""
    suffix = Path(filename).suffix.lower()
    return f"anhaenge/{instance.event_id}/{secrets.token_hex(12)}{suffix}"


class EventAttachment(models.Model):
    """Datei zu einer Veranstaltung, z. B. Ausschreibung oder Packliste. Liegt im Datenverzeichnis (ADR 0021)."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="attachments")
    title = models.CharField("Titel", max_length=120)
    file = models.FileField("Datei", upload_to=attachment_path, max_length=200)
    filename = models.CharField("Dateiname", max_length=200)
    size = models.PositiveIntegerField("Größe (Bytes)")
    public = models.BooleanField(
        "Für externe Teilnehmer sichtbar",
        default=False,
        help_text="Erscheint auch auf der Anmeldeseite für externe Teilnehmer, solange sie zugelassen sind.",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    uploaded_at = models.DateTimeField("Hochgeladen am", default=timezone.now, editable=False)

    class Meta:
        verbose_name = "Anhang"
        verbose_name_plural = "Anhänge"
        ordering = ("title", "pk")

    def __str__(self) -> str:
        return self.title

    @property
    def extension(self) -> str:
        return Path(self.filename).suffix.lower().lstrip(".")


class TargetGroup(Criteria):
    """Zielgruppe einer Veranstaltung. Anmelden kann sich, wer zu mindestens einer passt; ohne Zielgruppe alle."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="target_groups")
    name = models.CharField("Bezeichnung", max_length=80, blank=True, help_text="Optional, z. B. „U11“.")

    class Meta:
        verbose_name = "Zielgruppe"
        verbose_name_plural = "Zielgruppen"
        ordering = ("pk",)

    def __str__(self) -> str:
        return self.name or self.summary


class Weekday(models.IntegerChoices):
    MONDAY = 0, "Montag"
    TUESDAY = 1, "Dienstag"
    WEDNESDAY = 2, "Mittwoch"
    THURSDAY = 3, "Donnerstag"
    FRIDAY = 4, "Freitag"
    SATURDAY = 5, "Samstag"
    SUNDAY = 6, "Sonntag"


class Repeat(models.TextChoices):
    WEEKS = "weeks", "Alle x Wochen"
    MONTH = "month", "Jeden n-ten im Monat"


class WeekOfMonth(models.IntegerChoices):
    FIRST = 1, "1."
    SECOND = 2, "2."
    THIRD = 3, "3."
    FOURTH = 4, "4."
    LAST = -1, "letzten"


class Schedule(models.Model):
    """Zeitplan einer wiederkehrenden Veranstaltung, z. B. „Dienstag 17:00–18:30“ für einen Zeitraum.

    Rhythmus: alle x Wochen (gezählt ab „Gültig ab“) oder jeden n-ten Wochentag im Monat (z. B. 1. Samstag).
    """

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="schedules")
    weekday = models.PositiveSmallIntegerField("Wochentag", choices=Weekday.choices)
    repeat = models.CharField("Rhythmus", max_length=5, choices=Repeat.choices, default=Repeat.WEEKS)
    interval = models.PositiveSmallIntegerField(
        "Alle … Wochen",
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(52)],
        help_text="1 heißt jede Woche, 2 alle zwei Wochen. Gezählt ab „Gültig ab“.",
    )
    week_of_month = models.SmallIntegerField(
        "Welcher im Monat",
        choices=WeekOfMonth.choices,
        null=True,
        blank=True,
        help_text="Zum Beispiel 1. für den ersten Dienstag im Monat.",
    )
    start_time = models.TimeField("Beginn")
    end_time = models.TimeField("Ende")
    valid_from = models.DateField("Gültig ab")
    valid_until = models.DateField("Gültig bis", null=True, blank=True, help_text="Leer heißt: bis auf Weiteres.")
    opens_hours_before = models.PositiveSmallIntegerField(
        "Anmeldung öffnet (Stunden vorher)", null=True, blank=True, help_text="Leer heißt: sofort."
    )
    closes_hours_before = models.PositiveSmallIntegerField(
        "Anmeldung schließt (Stunden vorher)", null=True, blank=True, help_text="Leer heißt: zum Beginn."
    )
    generated_until = models.DateField(null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "Zeitplan"
        verbose_name_plural = "Zeitpläne"
        ordering = ("valid_from", "weekday", "start_time")

    def __str__(self) -> str:
        times = f"{self.start_time:%H:%M}–{self.end_time:%H:%M}"
        if self.repeat == Repeat.MONTH:
            nth = "Letzter" if self.week_of_month == WeekOfMonth.LAST else WeekOfMonth(self.week_of_month or 1).label
            return f"{nth} {self.get_weekday_display()} im Monat {times}"  # „1. Dienstag im Monat 17:00–18:30“
        if self.interval > 1:
            return f"{self.get_weekday_display()} {times}, {self.rhythm_label}"
        return f"{self.get_weekday_display()} {times}"

    @property
    def rhythm_label(self) -> str:
        """„jede Woche“, „alle 2 Wochen“, „jeden 1. Dienstag im Monat“, „jeden letzten Samstag im Monat“."""
        if self.repeat == Repeat.MONTH:
            nth = WeekOfMonth(self.week_of_month or 1).label
            return f"jeden {nth} {self.get_weekday_display()} im Monat"
        return "jede Woche" if self.interval == 1 else f"alle {self.interval} Wochen"


class Occurrence(models.Model):
    """Ein Termin. Aus einem Zeitplan erzeugt oder von Hand angelegt (Zusatztermin, einmalige Veranstaltung)."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="occurrences")
    schedule = models.ForeignKey(Schedule, on_delete=models.SET_NULL, null=True, blank=True, related_name="occurrences")
    starts_at = models.DateTimeField("Beginn")
    ends_at = models.DateTimeField("Ende")
    location = models.CharField("Abweichender Ort", max_length=120, blank=True)
    note = models.CharField("Hinweis", max_length=300, blank=True)
    registration_opens_at = models.DateTimeField("Anmeldung ab", null=True, blank=True, help_text="Leer heißt: sofort.")
    registration_closes_at = models.DateTimeField(
        "Anmeldeschluss", null=True, blank=True, help_text="Leer heißt: bis zum Beginn."
    )
    is_modified = models.BooleanField(default=False, editable=False)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    trainer_missing_since = models.DateTimeField(
        null=True, blank=True, editable=False, help_text="Der letzte Trainer hat sich ausgetragen (ADR 0018)."
    )
    custom_target_groups = models.BooleanField(
        "Zielgruppen weichen ab",
        default=False,
        editable=False,
        help_text="Der Termin hat eigene Zielgruppen statt der Zielgruppen der Veranstaltung (ADR 0019).",
    )

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
        return self.registration_opens_at

    @property
    def registration_closes(self) -> datetime:
        return self.registration_closes_at or self.starts_at

    def apply_rule(self, schedule: Schedule) -> None:
        """Anmeldezeitraum aus der Regel des Zeitplans (Stunden vor Beginn)."""
        opens, closes = schedule.opens_hours_before, schedule.closes_hours_before
        self.registration_opens_at = self.starts_at - timedelta(hours=opens) if opens is not None else None
        self.registration_closes_at = self.starts_at - timedelta(hours=closes) if closes is not None else None


class OccurrenceTargetGroup(Criteria):
    """Zielgruppe eines einzelnen Termins; gilt statt der Zielgruppen der Veranstaltung (ADR 0019)."""

    occurrence = models.ForeignKey(Occurrence, on_delete=models.CASCADE, related_name="target_groups")
    name = models.CharField("Bezeichnung", max_length=80, blank=True, help_text="Optional, z. B. „U11“.")

    class Meta:
        verbose_name = "Zielgruppe des Termins"
        verbose_name_plural = "Zielgruppen des Termins"
        ordering = ("pk",)

    def __str__(self) -> str:
        return self.name or self.summary


class ParticipantRole(models.Model):
    """Rolle an einem Termin: Teilnehmer, Trainer, Co-Trainer … pflegt die Abteilungsleitung (ADR 0012)."""

    name = models.CharField("Name", max_length=60, unique=True)
    order = models.PositiveSmallIntegerField("Reihenfolge", default=0)
    is_active = models.BooleanField("Aktiv", default=True)
    event_types = models.ManyToManyField(
        EventType,
        verbose_name="Veranstaltungsarten",
        blank=True,
        related_name="roles",
        help_text="Bei welchen Arten die Rolle angeboten wird. Nichts ausgewählt heißt: bei allen.",
    )
    user_roles = models.JSONField(
        "Benutzerrollen",
        default=list,
        blank=True,
        help_text="Wer die Rolle übernehmen darf. Nichts ausgewählt heißt: jedes Mitglied.",
    )
    is_team = models.BooleanField(
        "Übungsleiter-Rolle",
        default=False,
        help_text="Zählt nicht zur Höchstzahl, sieht die Teilnehmerliste eigener Termine und darf den Termin leiten.",
    )
    is_billable = models.BooleanField(
        "Abrechnungsrelevant",
        default=False,
        help_text="Die Stunden werden nach dem Termin bestätigt; Grundlage der Übungsleiterabrechnung.",
    )
    is_default = models.BooleanField(
        "Rolle bei Anmeldung",
        default=False,
        help_text="Diese Rolle bekommt, wer sich anmeldet oder angemeldet wird. Genau eine Rolle hat sie.",
    )

    class Meta:
        verbose_name = "Rolle"
        verbose_name_plural = "Rollen"
        ordering = ("order", "name")
        constraints = [
            models.UniqueConstraint(fields=["is_default"], condition=models.Q(is_default=True), name="one_default_role")
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args: Any, **kwargs: Any) -> None:
        ordering.append(self, "order")
        super().save(*args, **kwargs)

    def get_user_roles_display(self) -> str:
        from portal.accounts.models import Role

        return ", ".join(str(Role(role).label) for role in self.user_roles if role in Role.values) or "alle Mitglieder"


class Guest(models.Model):
    """Externer Gast einer Veranstaltung (ADR 0013). Ohne Zugang; sieht seine Daten über einen geheimen Link."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="guests")
    first_name = models.CharField("Vorname", max_length=60)
    last_name = models.CharField("Nachname", max_length=60)
    birth_year = models.PositiveSmallIntegerField(
        "Jahrgang", validators=[MinValueValidator(1900), MaxValueValidator(2100)]
    )
    gender = models.CharField("Geschlecht", max_length=1, choices=Gender.choices)
    grade = models.CharField("Graduierung", max_length=5, choices=Grade.choices, blank=True)
    weight = models.DecimalField(
        "Gewicht (kg)",
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(10), MaxValueValidator(250)],
    )
    club = models.CharField("Verein", max_length=120, blank=True)
    email = models.EmailField("E-Mail")
    phone = models.CharField("Telefon für Notfälle", max_length=40)
    guardian_name = models.CharField(
        "Erziehungsberechtigte", max_length=120, blank=True, help_text="Bei Minderjährigen: Name von Mutter oder Vater."
    )
    consent_at = models.DateTimeField("Datenschutz zugestimmt am")
    token = models.CharField(max_length=40, unique=True, editable=False)
    confirmed_at = models.DateTimeField("E-Mail bestätigt am", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        verbose_name = "Gast"
        verbose_name_plural = "Gäste"
        ordering = ("last_name", "first_name")

    def __str__(self) -> str:
        return self.display_name

    @property
    def display_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def birth_date(self) -> date:
        """Für das Zielgruppen-Matching zählt nur der Jahrgang."""
        return date(self.birth_year, 1, 1)

    @property
    def grade_short(self) -> str:
        return Grade(self.grade).short_label if self.grade else ""


class ParticipationStatus(models.TextChoices):
    PENDING = "pending", "Unbestätigt"
    REGISTERED = "registered", "Angemeldet"
    WAITLIST = "waitlist", "Warteliste"
    CANCELLED = "cancelled", "Abgemeldet"


class Participation(models.Model):
    """Teilnahme eines Mitglieds oder Gastes an einem Termin mit genau einer Rolle (Teilnehmer, Trainer …)."""

    occurrence = models.ForeignKey(Occurrence, on_delete=models.CASCADE, related_name="participations")
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="participations", null=True, blank=True)
    guest = models.ForeignKey(Guest, on_delete=models.CASCADE, related_name="participations", null=True, blank=True)
    role = models.ForeignKey(ParticipantRole, on_delete=models.PROTECT, related_name="participations")
    status = models.CharField("Status", max_length=10, choices=ParticipationStatus.choices)
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
    off_target = models.BooleanField(
        "Außerhalb der Zielgruppe",
        default=False,
        help_text="Selbst angemeldet, obwohl die Zielgruppe nur eine Empfehlung ist und nicht passt (ADR 0019).",
    )
    weight = models.DecimalField("Gewicht (kg)", max_digits=4, decimal_places=1, null=True, blank=True)
    note = models.CharField("Hinweis", max_length=200, blank=True)
    confirmed_at = models.DateTimeField("Bestätigt am", null=True, blank=True)
    minutes = models.PositiveIntegerField("Dauer (Minuten)", null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Teilnahme"
        verbose_name_plural = "Teilnahmen"
        ordering = ("created_at",)
        constraints = [
            models.UniqueConstraint(fields=["occurrence", "member"], name="participation_unique"),
            models.UniqueConstraint(fields=["occurrence", "guest"], name="participation_guest_unique"),
            models.CheckConstraint(
                condition=models.Q(member__isnull=False, guest__isnull=True)
                | models.Q(member__isnull=True, guest__isnull=False),
                name="participation_member_or_guest",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.person} – {self.occurrence} ({self.role}, {self.get_status_display()})"

    @property
    def person(self) -> Member | Guest:
        return self.member or self.guest  # type: ignore[return-value]

    @property
    def is_active(self) -> bool:
        return self.status in (ParticipationStatus.REGISTERED, ParticipationStatus.WAITLIST)

    @property
    def is_team(self) -> bool:
        return self.role.is_team

    @property
    def is_confirmed(self) -> bool:
        return self.confirmed_at is not None


class ScheduleTeam(models.Model):
    """Fest eingeteilte Übungsleiter eines Zeitplans; seine Termine übernehmen sie."""

    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, related_name="team")
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="schedule_teams")
    role = models.ForeignKey(ParticipantRole, on_delete=models.PROTECT, related_name="+")

    class Meta:
        verbose_name = "Fester Übungsleiter"
        verbose_name_plural = "Feste Übungsleiter"
        ordering = ("role__order", "member__first_name")
        constraints = [models.UniqueConstraint(fields=["schedule", "member"], name="schedule_team_unique")]

    def __str__(self) -> str:
        return f"{self.member} – {self.schedule} ({self.role})"


class QuickLink(models.Model):
    """Kurzer Code für einen Termin oder eine Veranstaltung, als Quick-Link und QR-Code für Ausschreibungen
    (ADR 0020). Der Code entsteht beim ersten Anzeigen."""

    code = models.CharField("Code", max_length=12, unique=True)
    event = models.OneToOneField(Event, on_delete=models.CASCADE, null=True, blank=True, related_name="quick_link")
    occurrence = models.OneToOneField(
        Occurrence, on_delete=models.CASCADE, null=True, blank=True, related_name="quick_link"
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        verbose_name = "Quick-Link"
        verbose_name_plural = "Quick-Links"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(event__isnull=False, occurrence__isnull=True)
                | models.Q(event__isnull=True, occurrence__isnull=False),
                name="quick_link_event_or_occurrence",
            )
        ]

    def __str__(self) -> str:
        return f"{self.code} → {self.event or self.occurrence}"
