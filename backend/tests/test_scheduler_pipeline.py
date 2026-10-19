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
        assert result["remaining_budget_boards"] == 39

        # Verify board was saved in DB
        from sqlalchemy import select
        b_res = await db_session.execute(select(GeneratedBoard).where(GeneratedBoard.game_type == "LOTTO"))
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

    # 1. Seed Draw in DB
    draw = Draw(
        draw_number=2710,
        game_type="LOTTO",
        draw_date=draw_date,
        numbers=[3, 7, 15, 22, 38, 49],
        bonus_ball=11,
    )
    db_session.add(draw)

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
        assert res["evaluated_boards_count"] >= 1

        # Verify board status updated to WON (4 matches >= 3)
        await db_session.refresh(board)
        assert board.status == BoardStatus.WON.value
        assert board.draw_id == draw.id

        # Verify BoardResult record created
        from sqlalchemy import select
        r_query = select(BoardResult).where(BoardResult.board_id == board.id)
        r_res = await db_session.execute(r_query)
        result_entity = r_res.scalar_one_or_none()
        assert result_entity is not None
        assert result_entity.matched_count == 4
        assert result_entity.matched_numbers == [3, 7, 15, 22]


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
