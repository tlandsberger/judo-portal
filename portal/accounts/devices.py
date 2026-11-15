"""Geräte erkennen: lesbarer Name aus dem User-Agent und Wiedererkennen bekannter Browser."""

from __future__ import annotations

import hashlib
import re

_BROWSERS = (
    ("Edg/", "Edge"),
    ("OPR/", "Opera"),
    ("SamsungBrowser/", "Samsung Internet"),
    ("Firefox/", "Firefox"),
    ("FxiOS/", "Firefox"),
    ("CriOS/", "Chrome"),
    ("Chrome/", "Chrome"),
    ("Safari/", "Safari"),
)
_SYSTEMS = (
    ("iPhone", "iPhone"),
    ("iPad", "iPad"),
    ("Android", "Android"),
    ("Windows", "Windows"),
    ("Mac OS X", "Mac"),
    ("CrOS", "ChromeOS"),
    ("Linux", "Linux"),
)


def describe(user_agent: str) -> str:
    """Zum Beispiel „Chrome auf Android“. Unbekanntes bleibt „Unbekannter Browser“."""
    browser = next((name for token, name in _BROWSERS if token in user_agent), "Unbekannter Browser")
    system = next((name for token, name in _SYSTEMS if token in user_agent), "")
    return f"{browser} auf {system}" if system else browser


def fingerprint(user_agent: str) -> str:
    """Browser wiedererkennen, ohne den User-Agent zu speichern. Versionsnummern zählen nicht (Updates)."""
    stable = re.sub(r"[\d._]+", "", user_agent)
    return hashlib.sha256(stable.encode()).hexdigest()[:32]
