"""Tests for persisted performance feedback and rolling outcome aggregation."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.board import BoardResult, GeneratedBoard
from app.models.draw import Draw
from app.models.feedback import GenerationFeedback
from app.schemas.board import PostDrawFeedbackResponse
from app.schemas.enums import GameType
from app.services.feedback_service import FeedbackService


def _feedback(accuracy: float, recommendations=None) -> PostDrawFeedbackResponse:
    return PostDrawFeedbackResponse(
        game_type=GameType.LOTTO,
        draw_date="2026-10-21",
        accuracy_rate=accuracy,
        divergence_analysis="Test divergence.",
        calibration_recommendations=recommendations or [],
    )


async def _seed(db_session, draw_number: int = 100, draw_date: date = date(2026, 10, 21)):
    draw = Draw(
        draw_number=draw_number,
        game_type="LOTTO",
        draw_date=draw_date,
        numbers=[1, 2, 3, 4, 5, 6],
        bonus_ball=7,
    )
    board = GeneratedBoard(
        bundle_name="LOTTO_FAMILY",
        game_type="LOTTO_FAMILY",
        target_draw_date=draw_date,
        numbers=[1, 2, 3, 4, 5, 8],
        confidence_score=80.0,
        ai_reasoning="Test board for feedback persistence.",
        status="WON",
        cost=Decimal("10.00"),
    )
    db_session.add_all([draw, board])
    await db_session.commit()
    await db_session.refresh(draw)
    await db_session.refresh(board)

    result = BoardResult(
        board_id=board.id,
        draw_id=draw.id,
        game_type="LOTTO",
        matched_numbers=[1, 2, 3, 4, 5],
        matched_count=5,
        matched_bonus=False,
        division="Division 3",
        prize_amount=Decimal("250.00"),
    )
    db_session.add(result)
    await db_session.commit()
    return draw, board, result


@pytest.mark.asyncio
async def test_record_feedback_computes_realized_roi(db_session):
    draw, board, result = await _seed(db_session)
    service = FeedbackService()

    record = await service.record_feedback(
        db_session,
        draw=draw,
        bundle_name="LOTTO_FAMILY",
        boards=[board],
        results=[result],
        feedback=_feedback(0.5, ["Increase high-number spread."]),
    )

    assert record.boards_evaluated == 1
    assert record.total_cost == Decimal("10.00")
    assert record.total_winnings == Decimal("250.00")
    assert record.roi_percentage == 2400.0
    assert record.calibration_recommendations == ["Increase high-number spread."]


@pytest.mark.asyncio
async def test_record_feedback_is_idempotent(db_session):
    draw, board, result = await _seed(db_session)
    service = FeedbackService()

    await service.record_feedback(
        db_session,
        draw=draw,
        bundle_name="LOTTO_FAMILY",
        boards=[board],
        results=[result],
        feedback=_feedback(0.33, ["First directive."]),
    )
    await service.record_feedback(
        db_session,
        draw=draw,
        bundle_name="LOTTO_FAMILY",
        boards=[board],
        results=[result],
        feedback=_feedback(0.67, ["Second directive."]),
    )

    rows = (
        await db_session.execute(
            select(GenerationFeedback).where(
                GenerationFeedback.draw_id == draw.id,
                GenerationFeedback.bundle_name == "LOTTO_FAMILY",
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].accuracy_rate == 0.67
    assert rows[0].calibration_recommendations == ["Second directive."]


@pytest.mark.asyncio
async def test_performance_summary_aggregates_window(db_session):
    service = FeedbackService()
    seed_dates = [date(2026, 10, 21), date(2026, 10, 24)]
    for idx, (accuracy, prize) in enumerate([(0.5, Decimal("0.00")), (0.75, Decimal("20.00"))]):
        draw, board, result = await _seed(db_session, draw_number=200 + idx, draw_date=seed_dates[idx])
        result.prize_amount = prize
        await db_session.commit()
        await service.record_feedback(
            db_session,
            draw=draw,
            bundle_name="LOTTO_FAMILY",
            boards=[board],
            results=[result],
            feedback=_feedback(accuracy, [f"Directive {idx}"]),
        )

    summary = await service.get_performance_summary(db_session, "LOTTO_FAMILY")

    assert summary.sample_count == 2
    assert summary.avg_accuracy == pytest.approx(0.625)
    assert summary.total_winnings == Decimal("20.00")
    assert summary.total_cost == Decimal("20.00")
    assert summary.net_profit == Decimal("0.00")
    assert summary.recent_recommendations == ["Directive 1", "Directive 0"]
    assert summary.has_sufficient_data is False


@pytest.mark.asyncio
async def test_performance_summary_empty(db_session):
    summary = await FeedbackService().get_performance_summary(
        db_session, "POWERBALL_FAMILY"
    )
    assert summary.sample_count == 0
    assert summary.has_sufficient_data is False
