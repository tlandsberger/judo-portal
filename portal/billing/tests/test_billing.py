"""Übungsleiterabrechnung: Sätze, Monate, Einreichen, Sperre, Freigabe (ADR 0014)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from portal.billing import services
from portal.billing.models import Claim, ClaimStatus
from portal.billing.services import BillingError
from portal.events import services as events
from portal.events.services import RegistrationError

from .conftest import make_shift, month_ago, role, set_rate

pytestmark = pytest.mark.django_db


def test_deadline():
    assert services.deadline(date(2026, 1, 1)) == date(2026, 4, 5)
    assert services.deadline(date(2026, 10, 1)) == date(2027, 1, 5)
    assert not services.is_overdue(date(2026, 1, 1), date(2026, 4, 5))
    assert services.is_overdue(date(2026, 1, 1), date(2026, 4, 6))
    assert services.months_due(date(2026, 4, 1)) == date(2026, 1, 1)


def test_rate_for_role_and_valid_from(trainer):
    member = events.own_member(trainer)
    set_rate(trainer, value="12.00", valid_from=date(2026, 1, 1))
    set_rate(trainer, value="15.00", valid_from=date(2026, 7, 1))
    trainer_role = role("Trainer")
    assert services.rate_for(member, trainer_role, date(2025, 12, 31)) is None
    assert services.rate_for(member, trainer_role, date(2026, 6, 30)).hourly_rate == Decimal("12.00")
    assert services.rate_for(member, trainer_role, date(2026, 7, 1)).hourly_rate == Decimal("15.00")
    assert services.rate_for(member, role("Co-Trainer"), date(2026, 7, 1)) is None  # kein Grundsatz


def test_amount_rounding():
    assert services.amount(90, Decimal("15.00")) == Decimal("22.50")
    assert services.amount(50, Decimal("13.33")) == Decimal("11.11")  # 11,108 → 11,11
    assert services.amount(45, Decimal("12.34")) == Decimal("9.26")  # 9,255 → 9,26 kaufmännisch


def test_month_overview(trainer):
    month = month_ago()
    set_rate(trainer)
    make_shift(trainer, month + timedelta(days=2))
    make_shift(trainer, month + timedelta(days=9), minutes=60)
    open_one = make_shift(trainer, month + timedelta(days=16), confirm=False)
    overview = services.month_overview(events.own_member(trainer), month)
    assert [line.minutes for line in overview.lines] == [90, 60]
    assert overview.total_amount == Decimal("37.50")
    assert overview.unconfirmed == [open_one]
    assert overview.can_submit and overview.status == "offen"


def test_submit_freezes_lines_and_locks(trainer):
    month = month_ago()
    set_rate(trainer)
    done = make_shift(trainer, month + timedelta(days=2))
    late = make_shift(trainer, month + timedelta(days=5), confirm=False)
    member = events.own_member(trainer)
    claim = services.submit(member, month, trainer)
    assert claim.status == ClaimStatus.SUBMITTED and claim.total_minutes == 90
    assert claim.total_amount == Decimal("22.50")
    line = claim.lines.get()
    assert (line.role_name, line.hourly_rate, line.amount) == ("Trainer", Decimal("15.00"), Decimal("22.50"))
    with pytest.raises(RegistrationError, match="eingereicht"):
        events.confirm(done, 120)
    with pytest.raises(RegistrationError, match="eingereicht"):
        events.confirm(late)
    with pytest.raises(BillingError, match="schon eingereicht"):
        services.submit(member, month, trainer)
    # Spätere Satzänderung ändert die eingereichte Abrechnung nicht.
    set_rate(trainer, value="20.00", valid_from=month)
    assert claim.lines.get().amount == Decimal("22.50")


def test_submit_rules(trainer):
    member = events.own_member(trainer)
    current = services.first_of_month(timezone.localdate())
    with pytest.raises(BillingError, match="nach Monatsende"):
        services.submit(member, current, trainer)
    with pytest.raises(BillingError, match="keine Stunden"):
        services.submit(member, month_ago(), trainer)
    make_shift(trainer, month_ago() + timedelta(days=1))
    with pytest.raises(BillingError, match="Für Trainer ist noch kein Satz"):
        services.submit(member, month_ago(), trainer)
    set_rate(trainer)
    assert services.submit(member, month_ago(), trainer).is_late is False


def test_late_submission_is_marked_and_stays_marked(trainer, head):
    member = events.own_member(trainer)
    set_rate(trainer)
    old = month_ago(4)  # Frist war der 5. des Vormonats
    make_shift(trainer, old + timedelta(days=1))
    overview = services.month_overview(member, old)
    assert overview.status == "überfällig" and overview.can_submit
    claim = services.submit(member, old, trainer)
    assert claim.is_late
    services.send_back(claim, head, "Bitte begründen")
    assert services.submit(member, old, trainer).is_late
    # Vor der Frist eingereicht, nach der Frist zurückgegeben: bleibt fristgerecht.
    make_shift(trainer, month_ago() + timedelta(days=1))
    on_time = services.submit(member, month_ago(), trainer)
    services.send_back(on_time, head, "Bitte prüfen")
    later = services.deadline(month_ago()) + timedelta(days=5)
    assert services.submit(member, month_ago(), trainer, today=later).is_late is False


def test_send_back_unlocks_and_resubmit(trainer, head):
    month = month_ago()
    set_rate(trainer)
    done = make_shift(trainer, month + timedelta(days=2))
    member = events.own_member(trainer)
    claim = services.submit(member, month, trainer)
    with pytest.raises(BillingError, match="Schreib"):
        services.send_back(claim, head, " ")
    services.send_back(claim, head, "Bitte 60 Minuten")
    events.confirm(done, 60)
    claim = services.submit(member, month, trainer)
    assert claim.total_minutes == 60 and claim.lines.count() == 1 and claim.feedback == "Bitte 60 Minuten"
    services.approve(claim, head)
    claim.refresh_from_db()
    assert claim.status == ClaimStatus.APPROVED and claim.decided_by_name == head.display_name
    with pytest.raises(BillingError):
        services.send_back(claim, head, "zu spät")


def test_department_head_can_approve_own_claim(head):
    from portal.members.models import LinkKind, MemberLink

    from .conftest import make_member

    MemberLink.objects.create(user=head, member=make_member("Lea", last_name="Leitung", age=40), kind=LinkKind.SELF)
    head.set_roles(["trainer", "department_head"])
    set_rate(head)
    make_shift(head, month_ago() + timedelta(days=3))
    claim = services.submit(events.own_member(head), month_ago(), head)
    services.approve(claim, head)
    assert Claim.objects.get().status == ClaimStatus.APPROVED


def test_rate_table_marks_missing(trainer, other_trainer, parent):
    set_rate(trainer)
    rows = services.rate_table()
    assert [row.member.first_name for row in rows] == ["Anna", "Ben"]
    anna, ben = rows
    assert [(r.name, rate is not None) for r, rate in anna.rates] == [("Trainer", True), ("Co-Trainer", False)]
    assert anna.missing and ben.missing


def test_unsubmitted_and_reminders(trainer, other_trainer, run_on_commit):
    from portal.billing import notices
    from portal.notifications.models import SentNotification

    month = month_ago()
    set_rate(trainer)
    make_shift(trainer, month + timedelta(days=2))
    make_shift(other_trainer, month + timedelta(days=2), confirm=False)
    assert [m.first_name for m in services.unsubmitted(month)] == ["Anna"]
    today = services.add_months(month, 1) + timedelta(days=0)  # der 1.
    run_on_commit(notices.remind, today)
    run_on_commit(notices.remind, today)
    assert SentNotification.objects.filter(kind="claim_remind").count() == 1
    run_on_commit(notices.remind, today + timedelta(days=1))  # der 2.: nichts
    assert SentNotification.objects.filter(kind="claim_remind").count() == 1
    last = services.add_months(month, 3) + timedelta(days=0)  # der 1. im Monat der Frist
    run_on_commit(notices.remind, last)
    assert SentNotification.objects.filter(kind="claim_remind", title__startswith="Frist bis 5.").count() == 1


def test_notices_on_submit_and_decide(trainer, head, run_on_commit):
    from portal.notifications.models import SentNotification

    set_rate(trainer)
    make_shift(trainer, month_ago() + timedelta(days=2))
    claim = run_on_commit(services.submit, events.own_member(trainer), month_ago(), trainer)
    assert SentNotification.objects.get(kind="claim_submitted").user == head
    run_on_commit(services.send_back, claim, head, "Bitte prüfen")
    assert SentNotification.objects.get(kind="claim_decided").user == trainer


def test_months_list_includes_unconfirmed(trainer):
    make_shift(trainer, month_ago() + timedelta(days=4), confirm=False)
    labels = [m.month for m in services.months(events.own_member(trainer))]
    assert labels == [services.first_of_month(timezone.localdate()), month_ago()]


def test_role_change_blocked_in_submitted_month(trainer):
    set_rate(trainer)
    make_shift(trainer, month_ago() + timedelta(days=2))
    open_one = make_shift(trainer, month_ago() + timedelta(days=5), confirm=False)
    member = events.own_member(trainer)
    services.submit(member, month_ago(), trainer)
    with pytest.raises(RegistrationError, match="eingereicht"):
        events.set_team(open_one.occurrence, member, role("Co-Trainer"))


def test_unconfirm_blocked_in_submitted_month(trainer):
    set_rate(trainer)
    shift = make_shift(trainer, month_ago() + timedelta(days=2))
    services.submit(events.own_member(trainer), month_ago(), trainer)
    with pytest.raises(RegistrationError, match="eingereicht"):
        events.unconfirm(shift)


def test_absent_blocked_in_submitted_month(trainer):
    set_rate(trainer)
    shift = make_shift(trainer, month_ago() + timedelta(days=2))
    services.submit(events.own_member(trainer), month_ago(), trainer)
    with pytest.raises(RegistrationError, match="eingereicht"):
        events.withdraw(shift, trainer)
    with pytest.raises(RegistrationError, match="eingereicht"):
        events.cancel_after(shift.occurrence, trainer)
