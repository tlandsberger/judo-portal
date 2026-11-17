"""Seiten der Abrechnung: Rechte, Einreichen, Freigeben, PDF, CSV, Stundensätze."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse

from portal.billing import services
from portal.billing.models import Claim, ClaimStatus, Rate
from portal.events import services as events
from portal.members.tests.conftest import PASSWORD

from .conftest import make_shift, month_ago, role, set_rate

pytestmark = pytest.mark.django_db


def login(client, user):
    assert client.login(email=user.email, password=PASSWORD)


def month_url(name, month):
    return reverse(name, args=[month.year, month.month])


def test_rights(client, trainer, parent, head):
    login(client, parent)
    assert client.get(reverse("billing_index")).status_code == 403
    assert client.get(reverse("claim_list")).status_code == 403
    assert client.get(reverse("rate_list")).status_code == 403
    login(client, trainer)
    assert client.get(reverse("billing_index")).status_code == 200
    assert client.get(reverse("claim_list")).status_code == 403
    login(client, head)
    assert client.get(reverse("billing_index")).url == reverse("claim_list")


def test_trainer_submits_month(client, trainer):
    set_rate(trainer)
    make_shift(trainer, month_ago() + timedelta(days=2))
    login(client, trainer)
    page = client.get(month_url("billing_month", month_ago()))
    assert "22,50 €" in page.content.decode() and "einreichen" in page.content.decode()
    response = client.post(month_url("billing_submit", month_ago()), follow=True)
    assert "ist eingereicht" in response.content.decode()
    assert Claim.objects.get().status == ClaimStatus.SUBMITTED


def test_correct_minutes_until_submitted(client, trainer):
    set_rate(trainer)
    shift = make_shift(trainer, month_ago() + timedelta(days=2))
    login(client, trainer)
    url = reverse("hours_confirm", args=[shift.occurrence_id])
    client.post(url, {"minutes": "60"})
    shift.refresh_from_db()
    assert shift.minutes == 60
    services.submit(events.own_member(trainer), month_ago(), trainer)
    response = client.post(url, {"minutes": "120"}, follow=True)
    assert "schon zur Abrechnung eingereicht" in response.content.decode()
    shift.refresh_from_db()
    assert shift.minutes == 60


def test_head_approves_and_downloads(client, trainer, other_trainer, head):
    set_rate(trainer)
    make_shift(trainer, month_ago() + timedelta(days=2))
    claim = services.submit(events.own_member(trainer), month_ago(), trainer)
    login(client, other_trainer)
    assert client.get(reverse("claim_detail", args=[claim.pk])).status_code == 403
    login(client, trainer)
    assert client.get(reverse("claim_detail", args=[claim.pk])).status_code == 200
    assert client.post(reverse("claim_approve", args=[claim.pk])).status_code == 403
    assert client.get(reverse("claim_pdf", args=[claim.pk])).status_code == 404  # noch nicht freigegeben
    login(client, head)
    assert "Zu prüfen" in client.get(reverse("claim_list")).content.decode()
    client.post(reverse("claim_approve", args=[claim.pk]))
    claim.refresh_from_db()
    assert claim.status == ClaimStatus.APPROVED
    pdf = client.get(reverse("claim_pdf", args=[claim.pk]))
    assert pdf["Content-Type"] == "application/pdf" and pdf.content.startswith(b"%PDF")
    csv = client.get(month_url("claim_csv", month_ago())).content.decode("utf-8-sig")
    assert csv.splitlines()[1].split(";")[1:3] == ["Trainer", "Anna"]
    assert csv.splitlines()[1].split(";")[4:6] == ["1,50", "22,50"]
    assert csv.splitlines()[1].split(";")[7] == "nein"
    login(client, trainer)
    assert client.get(reverse("claim_pdf", args=[claim.pk])).status_code == 200


def test_send_back_needs_feedback(client, trainer, head):
    set_rate(trainer)
    make_shift(trainer, month_ago() + timedelta(days=2))
    claim = services.submit(events.own_member(trainer), month_ago(), trainer)
    login(client, head)
    client.post(reverse("claim_send_back", args=[claim.pk]), {"feedback": ""})
    assert Claim.objects.get().status == ClaimStatus.SUBMITTED
    client.post(reverse("claim_send_back", args=[claim.pk]), {"feedback": "Bitte prüfen"})
    assert Claim.objects.get().status == ClaimStatus.RETURNED


def test_rates_pages(client, trainer, head):
    member = events.own_member(trainer)
    login(client, head)
    assert "kein Satz" in client.get(reverse("rate_list")).content.decode()
    url = reverse("rate_member", args=[member.pk])
    data = {"role": role("Trainer").pk, "hourly_rate": "15.00", "valid_from": "2026-01-01"}
    client.post(url, data)
    assert Rate.objects.get().hourly_rate == Decimal("15.00")
    response = client.post(url, data)
    assert "schon einen Satz" in response.content.decode()
    response = client.post(url, {**data, "role": role("Prüfer").pk})  # nicht abrechnungsrelevant
    assert Rate.objects.count() == 1
    client.post(reverse("rate_delete", args=[Rate.objects.get().pk]))
    assert not Rate.objects.exists()


def test_start_page_shows_pending_claims_for_head(client, trainer, head):
    set_rate(trainer)
    make_shift(trainer, month_ago() + timedelta(days=2))
    services.submit(events.own_member(trainer), month_ago(), trainer)
    login(client, head)
    assert "1 Abrechnung zu prüfen" in client.get(reverse("home")).content.decode()
    login(client, trainer)
    assert "zu prüfen" not in client.get(reverse("home")).content.decode()


def test_own_billing_has_no_link_to_claim_list(client, trainer):
    """„Meine Abrechnung“ und die Verwaltung „Abrechnungen“ sind getrennt – auch für Übungsleiter mit Leitungsrolle."""
    from portal.accounts.models import Role

    trainer.set_roles([Role.TRAINER, Role.DEPARTMENT_HEAD])
    trainer.save()
    login(client, trainer)
    main = client.get(reverse("billing_index")).content.decode().split("<aside", 1)[0]
    assert f'href="{reverse("claim_list")}"' not in main
    claims = client.get(reverse("claim_list")).content.decode().split("<aside", 1)[0]
    assert f'href="{reverse("billing_index")}"' not in claims
    assert reverse("rate_list") in claims
