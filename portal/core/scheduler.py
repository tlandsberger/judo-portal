"""Kleiner Zeitplaner im App-Prozess: nächtliches Backup und Aufräumen.

Läuft als Hintergrund-Thread im (einzigen) Gunicorn-Worker, so braucht es keinen zusätzlichen Container.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import date

from django.conf import settings
from django.contrib.sessions.models import Session
from django.db import close_old_connections
from django.utils import timezone

from . import backup

log = logging.getLogger(__name__)
_started = False


def run_daily_jobs(today: date) -> None:
    backup.create_backup(today)
    Session.objects.filter(expire_date__lt=timezone.now()).delete()


def _loop() -> None:
    last_run: date | None = None
    while True:
        try:
            now = timezone.localtime()
            today = now.date()
            if now.hour == settings.BACKUP_HOUR and last_run != today:
                if not backup.backup_path(today).exists():
                    run_daily_jobs(today)
                last_run = today
        except Exception:
            log.exception("Nächtliche Aufgaben fehlgeschlagen")
        finally:
            close_old_connections()
        time.sleep(60)


def start() -> None:
    global _started
    if _started:
        return
    _started = True
    threading.Thread(target=_loop, name="portal-scheduler", daemon=True).start()
    log.info("Zeitplaner gestartet (Backup täglich um %02d Uhr)", settings.BACKUP_HOUR)
