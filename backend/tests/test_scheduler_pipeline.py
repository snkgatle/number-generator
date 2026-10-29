"""Unit and integration tests for Phase 5 APScheduler Pipeline Orchestration."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch
import pytest

from app.models.board import BoardResult, GeneratedBoard
from app.models.budget import MonthlyBudget
from app.models.draw import Draw
from app.schemas.board import AIBoardRecommendation, AIGenerationResponse, PostDrawFeedbackResponse
from app.schemas.enums import BoardStatus, GameType
from app.scheduler.pipeline import PipelineOrchestrator


@pytest.fixture
def orchestrator():
    return PipelineOrchestrator()


@pytest.mark.asyncio
async def test_pre_draw_pipeline_execution(orchestrator, db_session):
    """Verify full Pre-Draw Pipeline flow (Stats -> AI -> Budget -> Save)."""
    mock_ai_resp = AIGenerationResponse(
        game_type=GameType.LOTTO,
        boards=[
            AIBoardRecommendation(
                numbers=[4, 12, 19, 23, 44, 51],
                bonus_or_powerball=None,
                confidence_score=88.0,
                reasoning="Test AI recommendation",
            )
        ],
        statistical_analysis_summary="Summary",
    )

    with patch.object(orchestrator.ai_service, "generate_boards", return_value=mock_ai_resp):
        result = await orchestrator.execute_pre_draw_pipeline(
            game_types=[GameType.LOTTO], target_date=date(2026, 10, 21), db=db_session
        )

        assert result["status"] == "COMPLETED"
        assert result["generated_boards_count"] == 1
        assert result["remaining_budget_boards"] == 19

        # Verify board was saved in DB
        from sqlalchemy import select
        b_res = await db_session.execute(select(GeneratedBoard).where(GeneratedBoard.bundle_name == "LOTTO_FAMILY"))
        saved = b_res.scalars().all()
        assert len(saved) >= 1
        assert saved[-1].numbers == [4, 12, 19, 23, 44, 51]
        assert saved[-1].status == BoardStatus.PENDING.value


@pytest.mark.asyncio
async def test_pre_draw_pipeline_circuit_breaker_halts(orchestrator, db_session):
    """Directive 3: Verify Pre-Draw Pipeline halts immediately if budget is exhausted."""
    # Seed exhausted budget
    ym = orchestrator.budget_engine.current_year_month()
    budget = MonthlyBudget(
        year_month=ym,
        total_budget=Decimal("200.00"),
        cost_per_board=Decimal("5.00"),
        total_boards=40,
        used_boards=40,
        remaining_boards=0,
        spent_amount=Decimal("200.00"),
        is_exhausted=True,
    )
    db_session.add(budget)
    await db_session.commit()

    result = await orchestrator.execute_pre_draw_pipeline(
        game_types=[GameType.LOTTO], target_date=date.today(), db=db_session
    )

    assert result["status"] == "HALTED"
    assert result["reason"] == "Budget Exhausted"
    assert result["generated_boards_count"] == 0


@pytest.mark.asyncio
async def test_post_draw_pipeline_evaluation(orchestrator, db_session):
    """Verify Post-Draw evaluation matches winning numbers and updates board status."""
    draw_date = date(2026, 10, 17)

    # 1. Seed all bundle sub-draws so the board can be finalized
    draw = Draw(
        draw_number=2710,
        game_type="LOTTO",
        draw_date=draw_date,
        numbers=[3, 7, 15, 22, 38, 49],
        bonus_ball=11,
    )
    db_session.add(draw)
    for idx, game_type in enumerate(["LOTTO_PLUS_1", "LOTTO_PLUS_2"], start=1):
        db_session.add(
            Draw(
                draw_number=2710 + idx,
                game_type=game_type,
                draw_date=draw_date,
                numbers=[1, 2, 3, 4, 5, 6],
                bonus_ball=7,
            )
        )

    # 2. Seed pending GeneratedBoard in DB matching 4 numbers
    board = GeneratedBoard(
        game_type="LOTTO",
        target_draw_date=draw_date,
        numbers=[3, 7, 15, 22, 40, 50],
        confidence_score=86.0,
        ai_reasoning="High probability low numbers.",
        status=BoardStatus.PENDING.value,
        cost=Decimal("5.00"),
    )
    db_session.add(board)
    await db_session.commit()
    await db_session.refresh(board)

    # Mock scraper & feedback
    mock_feedback = PostDrawFeedbackResponse(
        game_type=GameType.LOTTO,
        draw_date=draw_date.isoformat(),
        accuracy_rate=0.67,
        divergence_analysis="Good match in low quadrants.",
        calibration_recommendations=["Increase spread."],
    )

    with patch.object(orchestrator.scraper_service, "scrape_and_sync_all_games", return_value={"LOTTO": 0}), \
         patch.object(orchestrator.ai_service, "analyze_draw_performance", return_value=mock_feedback):

        res = await orchestrator.execute_post_draw_pipeline(db=db_session)
        assert res["status"] == "COMPLETED"
        # Honest counters: 1 distinct board, but it matched 3 Lotto-family sub-draws
        assert res["evaluated_boards_count"] == 1
        assert res["evaluated_sub_results"] == 3
        assert res["evaluated_draws_count"] == 3

        # Verify board status updated to WON (4 matches >= 3)
        await db_session.refresh(board)
        assert board.status == BoardStatus.WON.value
        assert board.draw_id == draw.id

        # Verify BoardResult record created
        from sqlalchemy import select
        r_query = select(BoardResult).where(
            BoardResult.board_id == board.id,
            BoardResult.game_type == "LOTTO",
        )
        r_res = await db_session.execute(r_query)
        result_entity = r_res.scalar_one_or_none()
        assert result_entity is not None
        assert result_entity.matched_count == 4
        assert result_entity.matched_numbers == [3, 7, 15, 22]

        # Feedback must be persisted for the bundle
        from app.models.feedback import GenerationFeedback
        f_res = await db_session.execute(
            select(GenerationFeedback).where(GenerationFeedback.draw_id == draw.id)
        )
        feedback_entity = f_res.scalar_one_or_none()
        assert feedback_entity is not None
        assert feedback_entity.bundle_name == "LOTTO_FAMILY"
        assert feedback_entity.boards_evaluated == 1


@pytest.mark.asyncio
async def test_manual_pipeline_api_triggers(client, db_session):
    """Verify POST /api/v1/generator/pipeline/pre-draw and /post-draw endpoints."""
    mock_pre_res = {
        "status": "COMPLETED",
        "target_date": "2026-10-21",
        "generated_boards_count": 1,
        "remaining_budget_boards": 38,
        "details": {},
    }
    mock_post_res = {
        "status": "COMPLETED",
        "evaluated_boards_count": 0,
        "evaluated_draws_count": 0,
        "feedback_summaries": {},
    }

    with patch("app.scheduler.pipeline_orchestrator.execute_pre_draw_pipeline", return_value=mock_pre_res), \
         patch("app.scheduler.pipeline_orchestrator.execute_post_draw_pipeline", return_value=mock_post_res):

        res1 = await client.post("/api/v1/generator/pipeline/pre-draw", json={"game_types": ["LOTTO"]})
        assert res1.status_code == 200
        assert res1.json()["status"] == "COMPLETED"

        res2 = await client.post("/api/v1/generator/pipeline/post-draw")
        assert res2.status_code == 200
        assert res2.json()["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_post_draw_skips_board_without_matching_draw_date(orchestrator, db_session):
    """High #5: Board must stay PENDING when no draw exists for its exact target date,
    rather than being evaluated against a later draw date.
    """
    # Seed a draw for a different date
    draw = Draw(
        draw_number=3000,
        game_type="LOTTO",
        draw_date=date(2026, 10, 25),
        numbers=[10, 20, 30, 40, 50, 52],
        bonus_ball=5,
    )
    db_session.add(draw)

    # Board targets a date with NO matching draw
    board = GeneratedBoard(
        game_type="LOTTO",
        bundle_name="LOTTO_FAMILY",
        target_draw_date=date(2026, 10, 18),
        numbers=[1, 2, 3, 4, 5, 6],
        confidence_score=85.0,
        ai_reasoning="Test board for stale evaluation prevention.",
        status=BoardStatus.PENDING.value,
        cost=Decimal("10.00"),
    )
    db_session.add(board)
    await db_session.commit()
    await db_session.refresh(board)

    with patch.object(orchestrator.scraper_service, "scrape_and_sync_all_games", return_value={"LOTTO": 0}):
        res = await orchestrator.execute_post_draw_pipeline(db=db_session)
        assert res["status"] == "COMPLETED"

    # Board must still be PENDING — no draw matched its exact target_date
    await db_session.refresh(board)
    assert board.status == BoardStatus.PENDING.value, (
        f"Expected PENDING, got {board.status}"
    )


@pytest.mark.asyncio
async def test_post_draw_defers_board_until_bundle_is_complete(orchestrator, db_session):
    """A board must not be finalized while some bundle sub-draws are missing."""
    draw_date = date(2026, 10, 24)
    board = GeneratedBoard(
        bundle_name="LOTTO_FAMILY",
        game_type="LOTTO_FAMILY",
        target_draw_date=draw_date,
        numbers=[1, 2, 3, 4, 5, 6],
        confidence_score=85.0,
        ai_reasoning="Awaiting complete bundle results.",
        status=BoardStatus.PENDING.value,
        cost=Decimal("10.00"),
    )
    db_session.add_all([
        Draw(
            draw_number=4000,
            game_type="LOTTO",
            draw_date=draw_date,
            numbers=[1, 2, 3, 4, 5, 6],
            bonus_ball=7,
        ),
        board,
    ])
    await db_session.commit()
    await db_session.refresh(board)

    with patch.object(orchestrator.scraper_service, "scrape_and_sync_all_games", return_value={"LOTTO": 0}):
        res = await orchestrator.execute_post_draw_pipeline(db=db_session)

    assert res["evaluated_boards_count"] == 0
    await db_session.refresh(board)
    assert board.status == BoardStatus.PENDING.value


@pytest.mark.asyncio
async def test_post_draw_persists_single_aggregated_bundle_feedback(orchestrator, db_session):
    """Directive 24: a Lotto-family night with 3 sub-draws yields ONE feedback
    row whose cost is charged once and whose winnings sum every sub-draw."""
    from app.models.feedback import GenerationFeedback
    from sqlalchemy import select

    draw_date = date(2026, 11, 18)  # a Wednesday
    board = GeneratedBoard(
        bundle_name="LOTTO_FAMILY",
        game_type="LOTTO_FAMILY",
        target_draw_date=draw_date,
        numbers=[3, 7, 15, 22, 40, 50],
        confidence_score=80.0,
        ai_reasoning="Aggregation regression board.",
        status=BoardStatus.PENDING.value,
        cost=Decimal("10.00"),
    )
    db_session.add(board)
    db_session.add_all([
        Draw(draw_number=5001, game_type="LOTTO", draw_date=draw_date,
             numbers=[3, 7, 15, 22, 38, 49], bonus_ball=11),
        Draw(draw_number=5002, game_type="LOTTO_PLUS_1", draw_date=draw_date,
             numbers=[3, 7, 15, 22, 40, 50], bonus_ball=1),
        Draw(draw_number=5003, game_type="LOTTO_PLUS_2", draw_date=draw_date,
             numbers=[3, 7, 15, 9, 10, 11], bonus_ball=2),
    ])
    await db_session.commit()
    await db_session.refresh(board)

    mock_feedback = PostDrawFeedbackResponse(
        game_type=GameType.LOTTO,
        draw_date=draw_date.isoformat(),
        accuracy_rate=0.5,
        divergence_analysis="Aggregated review.",
        calibration_recommendations=["Balance high/low."],
    )

    with patch.object(orchestrator.scraper_service, "scrape_and_sync_all_games", return_value={"LOTTO": 0}), \
         patch.object(orchestrator.ai_service, "analyze_draw_performance", return_value=mock_feedback) as mock_analyze:
        res = await orchestrator.execute_post_draw_pipeline(db=db_session)

    # AI review invoked once per bundle-date, not once per sub-draw
    assert mock_analyze.call_count == 1
    assert res["status"] == "COMPLETED"
    assert res["evaluated_boards_count"] == 1
    assert res["evaluated_sub_results"] == 3
    assert res["evaluated_draws_count"] == 3

    feedback_rows = (
        await db_session.execute(
            select(GenerationFeedback).where(GenerationFeedback.bundle_name == "LOTTO_FAMILY")
        )
    ).scalars().all()
    assert len(feedback_rows) == 1

    record = feedback_rows[0]
    assert record.boards_evaluated == 1
    assert record.total_cost == Decimal("10.00")  # charged once, not 3x

    # winnings equal the sum of all sub-draw BoardResult rows for this board
    results_rows = (
        await db_session.execute(
            select(BoardResult).where(BoardResult.board_id == board.id)
        )
    ).scalars().all()
    expected_winnings = sum((r.prize_amount for r in results_rows), Decimal("0.00"))
    assert len(results_rows) == 3
    assert record.total_winnings == expected_winnings
    assert record.roi_percentage == round(
        float((expected_winnings - Decimal("10.00")) / Decimal("10.00") * 100), 2
    )


@pytest.mark.asyncio
async def test_post_draw_sends_bundle_level_notification(orchestrator, db_session):
    """Directive 24: notifications are aggregated per bundle-night, not per sub-draw."""
    from unittest.mock import AsyncMock
    from sqlalchemy import select

    draw_date = date(2026, 11, 18)  # Wednesday (Lotto family night)
    board = GeneratedBoard(
        bundle_name="LOTTO_FAMILY", game_type="LOTTO_FAMILY",
        target_draw_date=draw_date, numbers=[3, 7, 15, 22, 40, 50],
        confidence_score=80.0, ai_reasoning="Bundle notification board.",
        status=BoardStatus.PENDING.value, cost=Decimal("10.00"),
    )
    db_session.add(board)
    db_session.add_all([
        Draw(draw_number=6001, game_type="LOTTO", draw_date=draw_date,
             numbers=[3, 7, 15, 22, 38, 49], bonus_ball=11),
        Draw(draw_number=6002, game_type="LOTTO_PLUS_1", draw_date=draw_date,
             numbers=[3, 7, 15, 22, 40, 50], bonus_ball=1),
        Draw(draw_number=6003, game_type="LOTTO_PLUS_2", draw_date=draw_date,
             numbers=[3, 7, 15, 22, 40, 50], bonus_ball=9),
    ])
    await db_session.commit()
    await db_session.refresh(board)

    mock_feedback = PostDrawFeedbackResponse(
        game_type=GameType.LOTTO, draw_date=draw_date.isoformat(),
        accuracy_rate=0.4, divergence_analysis="Bundle-level review.",
        calibration_recommendations=["Widen spread."],
    )

    with patch.object(orchestrator.scraper_service, "scrape_and_sync_all_games", return_value={"LOTTO": 0}), \
         patch.object(orchestrator.ai_service, "analyze_draw_performance", return_value=mock_feedback), \
         patch.object(orchestrator.notifier, "notify_bundle_completion", new_callable=AsyncMock) as mock_bundle, \
         patch.object(orchestrator.notifier, "notify_draw_completion", new_callable=AsyncMock) as mock_single, \
         patch.object(orchestrator.notifier, "notify_high_matches", new_callable=AsyncMock):

        await orchestrator.execute_post_draw_pipeline(db=db_session)

    # Exactly one bundle-level message; no per-sub-draw completion messages
    assert mock_bundle.call_count == 1
    assert mock_single.call_count == 0

    kwargs = mock_bundle.call_args.kwargs
    assert kwargs["bundle_name"] == "LOTTO_FAMILY"
    # Single board charged once
    assert kwargs["total_cost"] == Decimal("10.00")

    # Winnings equal the sum of every sub-draw result
    rows = (
        await db_session.execute(
            select(BoardResult).where(BoardResult.board_id == board.id)
        )
    ).scalars().all()
    expected = sum((r.prize_amount for r in rows), Decimal("0.00"))
    assert kwargs["total_winnings"] == expected
    assert len(rows) == 3
