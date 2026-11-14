"""Konsistente Schnappschüsse der SQLite-Datenbank für das Backup der Homecloud (restic sichert das Volume)."""

from __future__ import annotations

import logging
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from django.conf import settings
from django.db import connection

log = logging.getLogger(__name__)


def backup_path(day: date) -> Path:
    return Path(settings.BACKUP_DIR) / f"portal-{day.isoformat()}.sqlite3"


def create_backup(day: date | None = None) -> Path:
    """Schreibt einen Schnappschuss über die Backup-API von SQLite (auch bei laufendem Betrieb konsistent)."""
    day = day or date.today()
    target = backup_path(day)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    connection.ensure_connection()
    source = connection.connection
    with sqlite3.connect(tmp) as dest:
        source.backup(dest)
    dest.close()
    tmp.replace(target)
    prune_backups(day)
    log.info("Datenbank-Backup geschrieben: %s", target)
    return target


def prune_backups(today: date | None = None) -> None:
    cutoff = (today or date.today()) - timedelta(days=settings.BACKUP_KEEP_DAYS)
    for file in Path(settings.BACKUP_DIR).glob("portal-*.sqlite3"):
        try:
            day = date.fromisoformat(file.stem.removeprefix("portal-"))
        except ValueError:
            continue
        if day < cutoff:
            file.unlink()
