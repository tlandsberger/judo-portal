"""Anhänge an Veranstaltungen: hochladen, löschen, sichtbar machen und mit Rechteprüfung ausliefern (ADR 0021).

Die Dateien liegen unter ``MEDIA_ROOT`` (``/data/uploads``) und haben keine öffentliche URL. Mitglieder mit Zugang
sehen alle Anhänge; externe Teilnehmer nur die freigegebenen und nur, solange die Veranstaltung sie zulässt.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from django.core.files.uploadedfile import UploadedFile
from django.db.models.signals import post_delete
from django.http import FileResponse

from portal.core import audit

from .models import Event, EventAttachment

log = logging.getLogger(__name__)

MAX_SIZE = 10 * 1024 * 1024
# Endung → Inhaltstyp. PDF und Bilder öffnet der Browser direkt, der Rest kommt als Download.
TYPES = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".odt": "application/vnd.oasis.opendocument.text",
}
INLINE = {".pdf", ".jpg", ".jpeg", ".png"}
ACCEPT = ",".join(TYPES)


class AttachmentError(ValueError):
    pass


def check(upload: UploadedFile) -> None:
    suffix = Path(upload.name or "").suffix.lower()
    if suffix not in TYPES:
        raise AttachmentError("Erlaubt sind PDF, JPG, PNG, DOCX, XLSX und ODT.")
    if (upload.size or 0) > MAX_SIZE:
        raise AttachmentError("Die Datei ist zu groß (höchstens 10 MB).")
    if not upload.size:
        raise AttachmentError("Die Datei ist leer.")


def add(
    event: Event, upload: UploadedFile, *, title: str = "", public: bool = False, by: Any = None
) -> EventAttachment:
    check(upload)
    filename = Path(upload.name or "anhang").name[:200]
    attachment = EventAttachment(
        event=event,
        title=(title.strip() or Path(filename).stem)[:120],
        filename=filename,
        size=upload.size or 0,
        public=public and event.guests_welcome,
        uploaded_by=by if getattr(by, "pk", None) else None,
    )
    attachment.file.save(filename, upload, save=False)
    attachment.save()
    audit.log(by, audit.Area.EVENTS, "attachment_add", f"Anhang „{attachment.title}“ zu {event.title} hochgeladen")
    return attachment


def set_public(attachment: EventAttachment, public: bool, *, by: Any = None) -> None:
    attachment.public = public and attachment.event.guests_welcome
    attachment.save(update_fields=["public"])
    state = "für externe Teilnehmer sichtbar" if attachment.public else "nur für Mitglieder"
    audit.log(
        by, audit.Area.EVENTS, "attachment_public", f"Anhang „{attachment.title}“ zu {attachment.event.title} {state}"
    )


def delete(attachment: EventAttachment, *, by: Any = None) -> None:
    title, event = attachment.title, attachment.event
    attachment.delete()
    audit.log(by, audit.Area.EVENTS, "attachment_delete", f"Anhang „{title}“ zu {event.title} gelöscht")


def external(event: Event) -> list[EventAttachment]:
    """Anhänge für externe Teilnehmer: nur freigegebene und nur, wenn die Veranstaltung sie zulässt."""
    if not event.guests_welcome:
        return []
    return list(event.attachments.filter(public=True))


def response(attachment: EventAttachment) -> FileResponse:
    suffix = Path(attachment.filename).suffix.lower()
    return FileResponse(
        attachment.file.open("rb"),
        as_attachment=suffix not in INLINE,
        filename=attachment.filename,
        content_type=TYPES.get(suffix, "application/octet-stream"),
    )


def _remove_file(sender: object, instance: EventAttachment, **kwargs: object) -> None:
    """Datei mit dem Anhang löschen, auch wenn die ganze Veranstaltung gelöscht wird."""
    if instance.file:
        try:
            instance.file.delete(save=False)
        except OSError:
            log.warning("Datei %s ließ sich nicht löschen", instance.file.name)


def register_all() -> None:
    post_delete.connect(_remove_file, sender=EventAttachment, dispatch_uid="events_attachment_file")
