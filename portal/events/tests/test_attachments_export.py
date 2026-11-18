"""Anhänge an Veranstaltungen und Excel-Export der Teilnehmer (ADR 0021)."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from openpyxl import load_workbook

from portal.core.models import AuditEntry
from portal.events import attachments, guests, services
from portal.events.models import Event, EventAttachment, ParticipationStatus

from .conftest import PASSWORD, make_occurrence, role
from .test_guests import DATA

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def login(client, user):
    assert client.login(email=user.email, password=PASSWORD)
    return client


def pdf(name: str = "Ausschreibung.pdf", size: int = 100) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, b"%PDF-1.4 " + b"x" * size, content_type="application/pdf")


def body(response) -> bytes:
    return b"".join(response.streaming_content)


class TestAttachments:
    def test_head_uploads_members_download_file_is_removed(self, client, head, parent, child, tmp_path):
        event = Event.objects.create(title="Lehrgang")
        occurrence = make_occurrence(event)
        login(client, head)
        response = client.post(reverse("attachment_add", args=[event.pk]), {"file": pdf(), "title": ""}, follow=True)
        assert "„Ausschreibung“ hochgeladen." in response.content.decode()
        attachment = EventAttachment.objects.get()
        assert attachment.filename == "Ausschreibung.pdf" and attachment.size == 109
        stored = Path(attachment.file.path)
        assert stored.is_relative_to(tmp_path / "anhaenge" / str(event.pk)) and stored.name != "Ausschreibung.pdf"
        assert AuditEntry.objects.filter(action="attachment_add").exists()

        client.logout()
        login(client, parent)
        assert "Ausschreibung" in client.get(reverse("occurrence_detail", args=[occurrence.pk])).content.decode()
        response = client.get(reverse("attachment_download", args=[event.pk, attachment.pk]))
        assert response["Content-Type"] == "application/pdf" and body(response).startswith(b"%PDF")
        assert response["Content-Disposition"].startswith("inline")
        # Mitglieder dürfen nicht hochladen oder löschen
        assert client.post(reverse("attachment_add", args=[event.pk]), {"file": pdf()}).status_code == 403
        assert client.post(reverse("attachment_delete", args=[event.pk, attachment.pk])).status_code == 403

        client.logout()
        assert client.get(reverse("attachment_download", args=[event.pk, attachment.pk])).status_code == 302
        login(client, head)
        client.post(reverse("attachment_delete", args=[event.pk, attachment.pk]))
        assert not EventAttachment.objects.exists() and not stored.exists()

    def test_type_and_size_are_checked(self, head):
        event = Event.objects.create(title="Lehrgang")
        with pytest.raises(attachments.AttachmentError, match="Erlaubt sind"):
            attachments.add(event, SimpleUploadedFile("tool.exe", b"MZ"), by=head)
        with pytest.raises(attachments.AttachmentError, match="zu groß"):
            attachments.add(event, pdf(size=attachments.MAX_SIZE), by=head)
        docx = attachments.add(event, SimpleUploadedFile("Liste.DOCX", b"PK.."), title="Packliste", by=head)
        assert docx.title == "Packliste"
        assert attachments.response(docx)["Content-Disposition"].startswith("attachment")

    def test_files_go_with_the_event(self, head):
        event = Event.objects.create(title="Lehrgang")
        stored = Path(attachments.add(event, pdf(), by=head).file.path)
        event.delete()
        assert not stored.exists()

    def test_externals_see_only_public_attachments_while_allowed(self, client, head):
        event = Event.objects.create(title="Lehrgang", guests_welcome=True)
        token = guests.enable_link(event)
        occurrence = make_occurrence(event)
        public = attachments.add(event, pdf("Ausschreibung.pdf"), public=True, by=head)
        internal = attachments.add(event, pdf("Zimmerliste.pdf"), by=head)
        page = client.get(reverse("guest_register", args=[token])).content.decode()
        assert "Ausschreibung" in page and "Zimmerliste" not in page
        assert client.get(reverse("guest_attachment", args=[token, public.pk])).status_code == 200
        assert client.get(reverse("guest_attachment", args=[token, internal.pk])).status_code == 404

        guest = guests.register(event, DATA, [occurrence])
        page = client.get(reverse("guest_page", args=[guest.token])).content.decode()
        assert reverse("guest_attachment", args=[guest.token, public.pk]) in page
        assert client.get(reverse("guest_attachment", args=[guest.token, public.pk])).status_code == 200

        event.guests_welcome = False
        event.save()
        assert client.get(reverse("guest_attachment", args=[guest.token, public.pk])).status_code == 404
        assert attachments.add(event, pdf(), public=True, by=head).public is False

    def test_public_toggle_only_for_heads(self, client, head):
        event = Event.objects.create(title="Lehrgang", guests_welcome=True)
        attachment = attachments.add(event, pdf(), by=head)
        login(client, head)
        page = client.get(reverse("event_detail", args=[event.pk])).content.decode()
        assert "Für externe Teilnehmer sichtbar" in page
        assert 'type="file" name="file" class="file-input' in page  # DaisyUI File Input
        client.post(reverse("attachment_public", args=[event.pk, attachment.pk]), {"public": "1"})
        attachment.refresh_from_db()
        assert attachment.public


class TestExport:
    def test_occurrence_list_for_those_who_see_participants(self, client, head, trainer, parent, child):
        occurrence = make_occurrence(Event.objects.create(title="Randori"))
        services.register(occurrence, child, parent)
        services.set_team(occurrence, services.own_member(trainer), role("Trainer"), by=head)
        login(client, parent)
        assert client.get(reverse("occurrence_export", args=[occurrence.pk])).status_code == 403
        client.logout()
        login(client, trainer)
        response = client.get(reverse("occurrence_export", args=[occurrence.pk]))
        assert response.status_code == 200 and "attachment" in response["Content-Disposition"]
        sheet = load_workbook(BytesIO(response.content))["Teilnehmer"]
        rows = list(sheet.iter_rows(values_only=True))
        assert rows[0][:4] == ("Nachname", "Vorname", "Rolle", "Status")
        assert rows[1][:3] == ("Trainer", "Anna", "Trainer")
        assert rows[2][:4] == ("Muster", "Mia", "Teilnehmer", "Angemeldet")
        assert rows[2][13].startswith("Eltern")
        assert AuditEntry.objects.filter(action="export", actor=trainer).exists()

    def test_event_export_with_attendance_matrix(self, client, head, parent, child):
        event = Event.objects.create(title="Randori", capacity=1, guests_welcome=True)
        first, second = make_occurrence(event, in_days=2), make_occurrence(event, in_days=9)
        other = make_occurrence(event, in_days=400)
        services.register(first, child, parent)
        services.register(second, child, parent)
        guest = guests.register(event, DATA, [second])
        guests.confirm(guest)
        assert guest.participations.get().status == ParticipationStatus.WAITLIST

        login(client, parent)
        assert client.get(reverse("event_export", args=[event.pk])).status_code == 403
        client.logout()
        login(client, head)
        assert "Excel herunterladen" in client.get(reverse("event_export", args=[event.pk])).content.decode()
        end = (other.starts_at.date().replace(day=1)).isoformat()
        response = client.get(reverse("event_export", args=[event.pk]), {"start": "", "end": end})
        workbook = load_workbook(BytesIO(response.content))
        entries = list(workbook["Teilnahmen"].iter_rows(values_only=True))
        assert len(entries) == 4  # Kopf, Mia zweimal, Lena auf der Warteliste
        matrix = list(workbook["Anwesenheit"].iter_rows(values_only=True))
        assert len(matrix[0]) == 3 + 2 + 1  # Name, Rolle, zwei Termine im Zeitraum, Anzahl
        assert matrix[1] == ("Gast", "Lena", "Teilnehmer", None, "W", 0)
        assert matrix[2] == ("Muster", "Mia", "Teilnehmer", "x", "x", 2)
        assert AuditEntry.objects.filter(action="export", summary__contains="Randori").exists()
