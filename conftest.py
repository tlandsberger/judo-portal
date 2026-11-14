"""Gemeinsame Test-Einstellungen: kein Manifest für statische Dateien, Mails im Speicher, schnelles Hashing."""

import pytest


@pytest.fixture(autouse=True)
def _test_settings(settings, tmp_path):
    settings.STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    settings.BACKUP_DIR = tmp_path / "backups"
    settings.SECURE_SSL_REDIRECT = False
