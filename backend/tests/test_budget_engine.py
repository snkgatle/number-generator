"""Unit tests for Phase 5: BudgetEngine, Confidence-based allocation, and Circuit Breaker."""
from datetime import date
from decimal import Decimal
import pytest

from app.budget.engine import BudgetEngine, BudgetExhaustedException
from app.models.budget import MonthlyBudget
from app.schemas.enums import GameType


@pytest.fixture
def budget_engine():
    return BudgetEngine()


@pytest.mark.asyncio
async def test_monthly_budget_initialization(budget_engine, db_session):
    """Verify default monthly initialization: R200 budget = 40 boards."""
    current_ym = budget_engine.current_year_month()
    budget = await budget_engine.get_or_create_monthly_budget(db_session, year_month=current_ym)

    assert budget.year_month == current_ym
    assert budget.total_budget == Decimal("200.00")
    assert budget.cost_per_board == Decimal("10.00")
    assert budget.total_boards == 20
    assert budget.remaining_boards == 20
    assert budget.used_boards == 0
    assert budget.spent_amount == Decimal("0.00")
    assert budget.is_exhausted is False


@pytest.mark.asyncio
async def test_circuit_breaker_halts_when_exhausted(budget_engine, db_session):
    """Directive 3: Verify execution halts immediately if remaining_boards <= 0."""
    # Seed exhausted budget
    exhausted_budget = MonthlyBudget(
        year_month="2026-11",
        total_budget=Decimal("200.00"),
        cost_per_board=Decimal("5.00"),
        total_boards=40,
        used_boards=40,
        remaining_boards=0,
        spent_amount=Decimal("200.00"),
        is_exhausted=True,
    )
    db_session.add(exhausted_budget)
    await db_session.commit()

    with pytest.raises(BudgetExhaustedException) as exc:
        await budget_engine.check_circuit_breaker(db_session, boards_requested=1, year_month="2026-11")
    assert "Budget Exhausted" in str(exc.value)


@pytest.mark.asyncio
async def test_confidence_allocation_baseline(budget_engine, db_session):
    """Verify baseline 1 board allocation when confidence is normal or below 85%."""
    # Baseline with no confidence score
    rec = await budget_engine.calculate_confidence_allocation(
        db_session, game_type=GameType.LOTTO, target_date=date(2026, 10, 21), confidence_score=None
    )
    assert rec.base_boards == 1
    assert rec.bonus_boards == 0
    assert rec.total_allocated == 1

    # Baseline with confidence < 85% (e.g. 78%)
    rec_low = await budget_engine.calculate_confidence_allocation(
        db_session, game_type=GameType.LOTTO, target_date=date(2026, 10, 21), confidence_score=78.0
    )
    assert rec_low.base_boards == 1
    assert rec_low.bonus_boards == 0
    assert rec_low.total_allocated == 1


@pytest.mark.asyncio
async def test_confidence_allocation_bonus(budget_engine, db_session):
    """Verify bonus board allocation (+1 board) when confidence >= 85% and budget allows."""
    rec = await budget_engine.calculate_confidence_allocation(
        db_session, game_type=GameType.POWERBALL, target_date=date(2026, 10, 20), confidence_score=92.5
    )
    assert rec.base_boards == 1
    assert rec.bonus_boards == 1
    assert rec.total_allocated == 2
    assert "High confidence score" in rec.reasoning


@pytest.mark.asyncio
async def test_confidence_allocation_quota_capped(budget_engine, db_session):
    """Verify allocation is capped to remaining_boards when budget is nearly exhausted."""
    # Seed budget with only 1 board remaining
    low_budget = MonthlyBudget(
        year_month="2026-12",
        total_budget=Decimal("200.00"),
        cost_per_board=Decimal("5.00"),
        total_boards=40,
        used_boards=39,
        remaining_boards=1,
        spent_amount=Decimal("195.00"),
        is_exhausted=False,
    )
    db_session.add(low_budget)
    await db_session.commit()

    # Even with >85% confidence, cannot allocate 2 boards because remaining is 1
    rec = await budget_engine.calculate_confidence_allocation(
        db_session,
        game_type=GameType.LOTTO,
        target_date=date(2026, 12, 28),
        confidence_score=92.0,
    )
    assert rec.total_allocated == 1


@pytest.mark.asyncio
async def test_record_board_allocation(budget_engine, db_session):
    """Verify atomic quota deduction and circuit breaker tripping on exhaustion."""
    budget = await budget_engine.get_or_create_monthly_budget(db_session, year_month="2027-01")
    assert budget.remaining_boards == 20

    # Allocate 5 boards
    updated = await budget_engine.record_board_allocation(db_session, boards_count=5, year_month="2027-01")
    assert updated.used_boards == 5
    assert updated.remaining_boards == 15
    assert updated.spent_amount == Decimal("50.00")
    assert updated.is_exhausted is False

    # Allocate remaining 15 boards -> trips circuit breaker
    exhausted = await budget_engine.record_board_allocation(db_session, boards_count=15, year_month="2027-01")
    assert exhausted.used_boards == 20
    assert exhausted.remaining_boards == 0
    assert exhausted.spent_amount == Decimal("200.00")
    assert exhausted.is_exhausted is True


@pytest.mark.asyncio
async def test_allocation_plan_endpoint(client, db_session):
    """Verify GET /api/v1/dashboard/allocation-plan endpoint."""
    res = await client.get("/api/v1/dashboard/allocation-plan")
    assert res.status_code == 200
    data = res.json()
    assert "year_month" in data
    assert float(data["total_budget_zar"]) == 200.0
    assert data["total_boards"] == 20
    assert data["confidence_threshold"] == 90.0
    assert len(data["recommendations"]) >= 2


def test_cycle_date_range_resolution(budget_engine):
    """Verify that budget cycle resolves to the 25th of month M to 24th of month M+1."""
    # Test on the rollover day (25th)
    start, end, key = budget_engine.get_cycle_date_range(date(2026, 10, 25))
    assert start == date(2026, 10, 25)
    assert end == date(2026, 11, 24)
    assert key == "2026-10"

    # Test before rollover day (e.g. 24th) -> belongs to prior cycle
    start_prior, end_prior, key_prior = budget_engine.get_cycle_date_range(date(2026, 10, 24))
    assert start_prior == date(2026, 9, 25)
    assert end_prior == date(2026, 10, 24)
    assert key_prior == "2026-09"

    # Test mid-cycle date
    start_mid, end_mid, key_mid = budget_engine.get_cycle_date_range(date(2026, 11, 10))
    assert start_mid == date(2026, 10, 25)
    assert end_mid == date(2026, 11, 24)
    assert key_mid == "2026-10"

    # Year rollover: December 25th
    start_dec, end_dec, key_dec = budget_engine.get_cycle_date_range(date(2026, 12, 25))
    assert start_dec == date(2026, 12, 25)
    assert end_dec == date(2027, 1, 24)
    assert key_dec == "2026-12"

    # Year rollover: January 5th (belongs to December cycle)
    start_jan, end_jan, key_jan = budget_engine.get_cycle_date_range(date(2027, 1, 5))
    assert start_jan == date(2026, 12, 25)
    assert end_jan == date(2027, 1, 24)
    assert key_jan == "2026-12"


def test_cycle_draw_counting(budget_engine):
    """Verify that draw counts accurately reflect the 25th-to-24th cycle."""
    draws_info = budget_engine.calculate_remaining_draws_in_month(date(2026, 10, 25))
    assert draws_info["lotto_draws_total"] > 0
    assert draws_info["powerball_draws_total"] > 0
    assert draws_info["lotto_draws_remaining"] <= draws_info["lotto_draws_total"]
    assert draws_info["total_draws_remaining"] == (
        draws_info["lotto_draws_remaining"] + draws_info["powerball_draws_remaining"]
    )


def test_scheduler_rollover_day_registration():
    """Verify that APScheduler registers the monthly rollover job for day 25."""
    from app.core.config import settings
    from app.scheduler import scheduler
    from app.scheduler.tasks import register_scheduled_jobs

    register_scheduled_jobs()
    job = scheduler.get_job("lottomind_monthly_budget_rollover")
    assert job is not None
    # Trigger expression has day 25
    trigger_str = str(job.trigger)
    assert str(settings.BUDGET_CYCLE_ROLLOVER_DAY) in trigger_str

