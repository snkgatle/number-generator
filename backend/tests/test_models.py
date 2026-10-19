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
