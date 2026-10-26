"""Unit tests for SQLAlchemy models and database integrity constraints."""
from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select

from app.models.draw import Draw
from app.models.budget import MonthlyBudget
from app.models.board import GeneratedBoard, BoardResult


@pytest.mark.asyncio
async def test_draw_model_persistence(db_session):
    """Verify that a Draw model can be persisted and queried."""
    draw = Draw(
        draw_number=1337,
        game_type="LOTTO",
        draw_date=date(2026, 10, 15),
        numbers=[4, 12, 19, 23, 44, 51],
        bonus_ball=7,
        powerball=None,
    )
    db_session.add(draw)
    await db_session.commit()
    await db_session.refresh(draw)

    assert draw.id is not None
    assert draw.draw_number == 1337
    assert draw.numbers == [4, 12, 19, 23, 44, 51]
    assert draw.bonus_ball == 7


@pytest.mark.asyncio
async def test_draw_unique_constraint(db_session):
    """Directive 4: Verify unique constraint on (draw_number, game_type)."""
    draw1 = Draw(
        draw_number=100,
        game_type="LOTTO",
        draw_date=date(2026, 10, 1),
        numbers=[1, 2, 3, 4, 5, 6],
    )
    db_session.add(draw1)
    await db_session.commit()

    draw2 = Draw(
        draw_number=100,
        game_type="LOTTO",  # Duplicate draw_number + game_type
        draw_date=date(2026, 10, 1),
        numbers=[7, 8, 9, 10, 11, 12],
    )
    db_session.add(draw2)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_monthly_budget_defaults_and_limits(db_session):
    """Verify MonthlyBudget creation, defaults, and relationships."""
    budget = MonthlyBudget(
        year_month="2026-10",
        total_budget=Decimal("200.00"),
        cost_per_board=Decimal("5.00"),
        total_boards=40,
        remaining_boards=40,
        used_boards=0,
    )
    db_session.add(budget)
    await db_session.commit()
    await db_session.refresh(budget)

    assert budget.id is not None
    assert budget.remaining_boards == 40
    assert budget.is_exhausted is False
    assert budget.total_budget == Decimal("200.00")


@pytest.mark.asyncio
async def test_generated_board_and_result_relationship(db_session):
    """Verify relationships between MonthlyBudget, GeneratedBoard, Draw, and BoardResult."""
    # 1. Setup Budget
    budget = MonthlyBudget(
        year_month="2026-10",
        total_budget=Decimal("200.00"),
        remaining_boards=39,
        used_boards=1,
    )
    db_session.add(budget)
    await db_session.commit()

    # 2. Setup Draw
    draw = Draw(
        draw_number=501,
        game_type="POWERBALL",
        draw_date=date(2026, 10, 17),
        numbers=[5, 14, 22, 33, 49],
        powerball=12,
    )
    db_session.add(draw)
    await db_session.commit()

    # 3. Create Board
    board = GeneratedBoard(
        budget_id=budget.id,
        draw_id=draw.id,
        game_type="POWERBALL",
        target_draw_date=date(2026, 10, 17),
        numbers=[5, 14, 22, 33, 48],  # 4 matched
        bonus_or_powerball=12,         # Powerball matched
        confidence_score=88.5,
        ai_reasoning="Strong distribution along historical cold numbers.",
        status="EVALUATED",
    )
    db_session.add(board)
    await db_session.commit()
    await db_session.refresh(board)

    # 4. Create Result
    result = BoardResult(
        board_id=board.id,
        draw_id=draw.id,
        matched_numbers=[5, 14, 22, 33],
        matched_count=4,
        matched_bonus=True,
        division="Division 3",
        prize_amount=Decimal("1500.00"),
    )
    db_session.add(result)
    await db_session.commit()
    await db_session.refresh(board)

    assert board.result is not None
    assert board.result.matched_count == 4
    assert board.result.matched_bonus is True
    assert board.result.prize_amount == Decimal("1500.00")


@pytest.mark.asyncio
async def test_temporal_analytics_model(db_session):
    """Directive 11: Verify TemporalAnalytics model persistence with JSON co-occurrence and frequency maps."""
    from app.models.analytics import TemporalAnalytics

    analytics = TemporalAnalytics(
        game_type="LOTTO",
        timeframe="WEEKLY",
        analysis_date=date(2026, 10, 21),
        sample_draws_count=8,
        sum_average=142.5,
        sum_std_dev=18.2,
        parity_ratio="3.1:2.9",
        frequency_map={"7": 4, "14": 3, "22": 5},
        co_occurrence_matrix={"7-14": 2, "7-22": 3},
        actionable_bias_for_generation={"favored_parity": "3:3", "suggested_sum_range": [130, 160]},
        ai_insights="Strong clustering around median numbers with standard parity distribution.",
    )
    db_session.add(analytics)
    await db_session.commit()
    await db_session.refresh(analytics)

    assert analytics.id is not None
    assert analytics.game_type == "LOTTO"
    assert analytics.timeframe == "WEEKLY"
    assert analytics.frequency_map["22"] == 5
    assert analytics.co_occurrence_matrix["7-22"] == 3
    assert analytics.actionable_bias_for_generation["suggested_sum_range"] == [130, 160]
    assert "clustering" in analytics.ai_insights


@pytest.mark.asyncio
async def test_game_bundle_model_and_multi_results(db_session):
    """Directive 21 & 24: Test GameBundle model, 1-to-many BoardResult relationship, and total_prize property."""
    from app.models.bundle import GameBundle

    # 1. Create GameBundle
    bundle = GameBundle(
        bundle_name="LOTTO_FAMILY",
        main_matrix_rule="6/52",
        addon_matrix_rule="1/52 Bonus Ball",
        total_cost_per_board=Decimal("10.00"),
    )
    db_session.add(bundle)
    await db_session.commit()
    await db_session.refresh(bundle)
    assert bundle.id is not None
    assert bundle.total_cost_per_board == Decimal("10.00")

    # 2. Create GeneratedBoard linked to bundle
    board = GeneratedBoard(
        bundle_id=bundle.id,
        bundle_name="LOTTO_FAMILY",
        target_draw_date=date(2026, 10, 21),
        numbers=[3, 15, 22, 31, 40, 52],
        confidence_score=91.5,
        cost=Decimal("10.00"),
        status="PENDING",
    )
    db_session.add(board)
    await db_session.commit()
    await db_session.refresh(board)
    assert board.bundle_id == bundle.id

    # 3. Create Draws for 2 sub-games on same date
    draw1 = Draw(draw_number=201, game_type="LOTTO", draw_date=date(2026, 10, 21), numbers=[3, 15, 22, 1, 2, 4])
    draw2 = Draw(draw_number=202, game_type="LOTTO_PLUS_1", draw_date=date(2026, 10, 21), numbers=[3, 15, 22, 31, 40, 52])
    db_session.add_all([draw1, draw2])
    await db_session.commit()

    # 4. Create multiple BoardResults for the single board (Directive 24)
    res1 = BoardResult(
        board_id=board.id,
        draw_id=draw1.id,
        game_type="LOTTO",
        matched_numbers=[3, 15, 22],
        matched_count=3,
        matched_bonus=False,
        prize_amount=Decimal("50.00"),
    )
    res2 = BoardResult(
        board_id=board.id,
        draw_id=draw2.id,
        game_type="LOTTO_PLUS_1",
        matched_numbers=[3, 15, 22, 31, 40, 52],
        matched_count=6,
        matched_bonus=False,
        prize_amount=Decimal("3500000.00"),
    )
    db_session.add_all([res1, res2])
    await db_session.commit()
    await db_session.refresh(board)

    # 5. Verify 1-to-many relationship and total_prize property
    assert len(board.results) == 2
    assert board.total_prize == Decimal("3500050.00")


def test_config_guards_default_jwt_secret_in_production():
    """High #7: Settings must refuse to load in production with the default JWT_SECRET_KEY."""
    import os
    from app.core.config import Settings

    with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="lottomind-insecure-dev-secret-key-change-in-production-min32chars",
            _env_file=None,
        )

    # Should succeed with a non-default key in production
    settings = Settings(
        ENVIRONMENT="production",
        JWT_SECRET_KEY="a-very-strong-production-secret-key-min-32-chars",
        _env_file=None,
    )
    assert settings.JWT_SECRET_KEY == "a-very-strong-production-secret-key-min-32-chars"
