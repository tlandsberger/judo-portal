"""Kleiner Zeitplaner im App-Prozess: nächtliches Backup und Aufräumen, kurze Jobs alle 10 Minuten.

Läuft als Hintergrund-Thread im (einzigen) Gunicorn-Worker, so braucht es keinen zusätzlichen Container.
Fach-Apps melden ihre Jobs in ``AppConfig.ready()`` an (``register_daily``, ``register_periodic``); ``portal.core``
kennt sie nicht.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from datetime import date

from django.conf import settings
from django.contrib.sessions.models import Session
from django.db import close_old_connections
from django.utils import timezone

from . import backup

log = logging.getLogger(__name__)
_started = False
PERIODIC_SECONDS = 10 * 60
_daily: list[Callable[[], None]] = []
_periodic: list[Callable[[], None]] = []


def register_daily(job: Callable[[], None]) -> None:
    """Job für die Nacht (nach dem Backup)."""
    if job not in _daily:
        _daily.append(job)


def register_periodic(job: Callable[[], None]) -> None:
    """Kurzer Job alle 10 Minuten, z. B. Erinnerungen. Muss idempotent sein."""
    if job not in _periodic:
        _periodic.append(job)


def _run(jobs: list[Callable[[], None]]) -> None:
    for job in jobs:
        try:
            job()
        except Exception:
            log.exception("Job %s fehlgeschlagen", getattr(job, "__qualname__", job))
        finally:
            close_old_connections()


def run_daily_jobs(today: date) -> None:
    backup.create_backup(today)
    Session.objects.filter(expire_date__lt=timezone.now()).delete()
    _run(_daily)


def run_periodic_jobs() -> None:
    _run(_periodic)


def _loop() -> None:
    last_run: date | None = None
    last_periodic = 0.0
    while True:
        if time.monotonic() - last_periodic >= PERIODIC_SECONDS:
            last_periodic = time.monotonic()
            run_periodic_jobs()
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
