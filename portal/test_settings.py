"""Einstellungen für pytest: setzt die nötigen Umgebungsvariablen und übernimmt sonst alles aus settings.py."""

import os
import tempfile

os.environ.setdefault("PORTAL_SECRET_KEY", "test-secret-key")
os.environ.setdefault("PORTAL_DATA_DIR", tempfile.mkdtemp(prefix="portal-test-"))
os.environ.setdefault("PORTAL_BASE_URL", "https://judo.example.org")
os.environ.setdefault("PORTAL_ALLOWED_HOSTS", "testserver,judo.example.org")

from portal.settings import *  # noqa: F403
