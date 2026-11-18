"""Benutzer, Rollen und Einladungen.

Ein Benutzer ist bewusst getrennt vom Vereinsmitglied: Verknüpfungen (eigenes Profil, Erziehungsberechtigt …)
liegen in ``portal.members`` (``MemberLink``, m:n, ADR 0003).
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import ClassVar

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class Role(models.TextChoices):
    """Feste Rollen nach Vereinsfunktionen. Eltern sind keine Rolle, sondern verknüpfte Benutzer."""

    MEMBER = "member", "Mitglied"
    TRAINER = "trainer", "Übungsleiter"
    DEPARTMENT_HEAD = "department_head", "Abteilungsleiter"
    ADMIN = "admin", "Administrator"


class UserManager(BaseUserManager["User"]):
    use_in_migrations = True

    def create_user(self, email: str, password: str | None = None, **extra: object) -> User:
        if not email:
            raise ValueError("Eine E-Mail-Adresse ist erforderlich.")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra: object) -> User:
        user = self.create_user(email, password, **extra)
        user.set_roles([Role.ADMIN])
        return user


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField("E-Mail", unique=True)
    first_name = models.CharField("Vorname", max_length=100, blank=True)
    last_name = models.CharField("Nachname", max_length=100, blank=True)
    phone = models.CharField(
        "Telefon", max_length=40, blank=True, help_text="Für Notfälle bei Terminen; sehen nur begleitende Übungsleiter."
    )
    roles = models.JSONField("Rollen", default=list, blank=True)
    is_active = models.BooleanField("Aktiv", default=True)
    is_staff = models.BooleanField("Zugang zur technischen Verwaltung", default=False)
    date_joined = models.DateTimeField("Angelegt am", default=timezone.now)

    objects: ClassVar[UserManager] = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    class Meta:
        verbose_name = "Benutzer"
        verbose_name_plural = "Benutzer"
        ordering = ("last_name", "first_name", "email")

    def __str__(self) -> str:
        return self.display_name

    @property
    def display_name(self) -> str:
        name = f"{self.first_name} {self.last_name}".strip()
        return name or self.email

    def get_full_name(self) -> str:
        return self.display_name

    def get_short_name(self) -> str:
        return self.first_name or self.email

    @property
    def greeting(self) -> str:
        """Anrede für Mails und Startseite, z. B. „Hallo Anna“ oder „Liebe Eltern von Mia“."""
        from .services import greeting

        return greeting(user=self)

    def has_role(self, *roles: Role | str) -> bool:
        return self.is_active and any(str(role) in self.roles for role in roles)

    @property
    def role_labels(self) -> list[str]:
        return [Role(r).label for r in Role.values if r in self.roles]

    def set_roles(self, roles: list[Role] | list[str]) -> None:
        """Setzt die Rollen; Administratoren erhalten zusätzlich die technische Verwaltung (Django-Admin)."""
        self.roles = [r for r in Role.values if r in {str(x) for x in roles}]
        admin = Role.ADMIN.value in self.roles
        self.is_staff = admin
        self.is_superuser = admin
        self.save(update_fields=["roles", "is_staff", "is_superuser"] if self.pk else None)


def _new_token() -> str:
    return secrets.token_urlsafe(32)


def _default_expiry() -> datetime:
    return timezone.now() + timedelta(days=settings.INVITATION_DAYS)


class Invitation(models.Model):
    """Einladung per Mail. Der Link meldet die Person an und führt zur Einrichtung ihrer Anmeldewege."""

    email = models.EmailField("E-Mail")
    first_name = models.CharField("Vorname", max_length=100, blank=True)
    last_name = models.CharField("Nachname", max_length=100, blank=True)
    roles = models.JSONField("Rollen", default=list, blank=True)
    token = models.CharField(max_length=64, unique=True, default=_new_token, editable=False)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(default=_default_expiry)
    accepted_at = models.DateTimeField(null=True, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="invitations"
    )

    class Meta:
        verbose_name = "Einladung"
        verbose_name_plural = "Einladungen"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Einladung an {self.email}"

    @property
    def is_valid(self) -> bool:
        return self.accepted_at is None and self.expires_at > timezone.now()

    def renew(self) -> None:
        """Neuer Link und neue Frist, der alte Link wird ungültig."""
        self.token = _new_token()
        self.created_at = timezone.now()
        self.expires_at = _default_expiry()
        self.save(update_fields=["token", "created_at", "expires_at"])


class KnownDevice(models.Model):
    """Browser, mit dem sich ein Benutzer schon angemeldet hat. Gespeichert wird nur ein Fingerabdruck (ADR 0011)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="known_devices")
    fingerprint = models.CharField(max_length=64)
    description = models.CharField("Gerät", max_length=100, blank=True)
    first_seen = models.DateTimeField(default=timezone.now)
    last_seen = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Bekanntes Gerät"
        verbose_name_plural = "Bekannte Geräte"
        constraints = [models.UniqueConstraint(fields=["user", "fingerprint"], name="known_device_unique")]

    def __str__(self) -> str:
        return f"{self.user} – {self.description}"
