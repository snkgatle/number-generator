"""Unit and integration tests for Qwen-Max AI integration, prompt synthesis, and router."""
from datetime import date
from decimal import Decimal
from http import HTTPStatus
from unittest.mock import MagicMock, patch
import pytest

from app.models.board import GeneratedBoard, BoardResult
from app.models.budget import MonthlyBudget
from app.models.draw import Draw
from app.schemas.board import AIBoardRecommendation, AIGenerationResponse
from app.schemas.enums import GameType
from app.services.ai_service import AIService, AIServiceError


@pytest.fixture
def ai_service():
    return AIService(api_key="test_dashscope_key")


def test_clean_json_markdown():
    """Verify markdown code block cleanup from raw LLM output."""
    raw_with_fences = "```json\n{\"key\": \"value\"}\n```"
    assert AIService.clean_json_markdown(raw_with_fences) == '{"key": "value"}'

    raw_plain = "{\"key\": \"value\"}"
    assert AIService.clean_json_markdown(raw_plain) == '{"key": "value"}'


@pytest.mark.asyncio
async def test_generate_boards_success(ai_service):
    """Verify successful board generation and Pydantic validation with Qwen-Max."""
    mock_payload = {
        "game_type": "LOTTO",
        "boards": [
            {
                "numbers": [4, 12, 19, 23, 44, 51],
                "bonus_or_powerball": None,
                "confidence_score": 87.5,
                "reasoning": "Strong alignment with recent 3:3 odd/even ratio and hot numbers 4, 12, 44.",
            }
        ],
        "statistical_analysis_summary": "Evaluated last 50 draws; balanced distribution.",
    }

    with patch.object(ai_service, "call_qwen_json", return_value=mock_payload):
        response = await ai_service.generate_boards(
            game_type=GameType.LOTTO,
            target_draw_date=date(2026, 10, 21),
            allocated_boards=1,
            stats_context={
                "hot_numbers": "4, 12, 44",
                "cold_numbers": "1, 2, 52",
                "odd_even_ratio": "3:3",
                "consecutive_pairs": "None",
                "overdue_numbers": "7, 13",
            },
        )

        assert response.game_type == GameType.LOTTO
        assert len(response.boards) == 1
        assert response.boards[0].numbers == [4, 12, 19, 23, 44, 51]
        assert response.boards[0].confidence_score == 87.5


@pytest.mark.asyncio
async def test_generate_boards_powerball_validation(ai_service):
    """Verify PowerBall game matrix rule enforcement (5 numbers 1-50, powerball 1-16)."""
    # Invalid Powerball number 25 (> 16)
    mock_payload = {
        "game_type": "POWERBALL",
        "boards": [
            {
                "numbers": [10, 20, 30, 40, 50],
                "bonus_or_powerball": 25,
                "confidence_score": 80.0,
                "reasoning": "Invalid test board",
            }
        ],
        "statistical_analysis_summary": "Testing validation",
    }

    with patch.object(ai_service, "call_qwen_json", return_value=mock_payload):
        with pytest.raises(AIServiceError) as exc:
            await ai_service.generate_boards(
                game_type=GameType.POWERBALL,
                target_draw_date=date(2026, 10, 20),
                allocated_boards=1,
                stats_context={},
                fallback_on_error=False,
            )
        assert "powerball 25 out of bounds" in str(exc.value)
        assert "1-16" in str(exc.value)


@pytest.mark.asyncio
async def test_generate_boards_graceful_degradation_tier2(ai_service):
    """Directive 13: When Qwen-Max fails or returns invalid output, gracefully fall back to Tier 2 statistical."""
    # Mock Qwen failure
    with patch.object(ai_service, "call_qwen_json", side_effect=Exception("Qwen API Network Timeout")):
        response = await ai_service.generate_boards(
            game_type=GameType.LOTTO,
            target_draw_date=date(2026, 10, 21),
            allocated_boards=2,
            stats_context={
                "hot_numbers": "1, 2, 3, 4, 5, 6, 7, 8, 9, 10",
                "cold_numbers": "40, 41, 42, 43, 44, 45",
            },
            fallback_on_error=True,
        )

        assert response.game_type == GameType.LOTTO
        assert len(response.boards) == 2
        for b in response.boards:
            assert len(b.numbers) == 6
            assert len(set(b.numbers)) == 6
            assert "statistical fallback" in b.reasoning.lower()
            assert b.confidence_score == 70.0


@pytest.mark.asyncio
async def test_generate_boards_graceful_degradation_tier3_secrets_random(ai_service):
    """Directive 13: When Tier 2 statistical generation fails, fall back to Tier 3 secrets random generation."""
    with patch.object(ai_service, "call_qwen_json", side_effect=Exception("Qwen Down")):
        with patch.object(ai_service, "generate_statistical_fallback", side_effect=Exception("Stats Engine Down")):
            response = await ai_service.generate_boards(
                game_type=GameType.POWERBALL,
                target_draw_date=date(2026, 10, 20),
                allocated_boards=2,
                stats_context={},
                fallback_on_error=True,
            )

            assert response.game_type == GameType.POWERBALL
            assert len(response.boards) == 2
            for b in response.boards:
                assert len(b.numbers) == 5
                assert len(set(b.numbers)) == 5
                assert 1 <= b.bonus_or_powerball <= 16
                assert "secrets module" in b.reasoning.lower()
                assert b.confidence_score == 50.0


@pytest.mark.asyncio
async def test_analyze_draw_performance(ai_service):
    """Verify Post-Draw Feedback Loop prompt formatting and response parsing."""
    draw = Draw(
        id=1,
        draw_number=2690,
        game_type="LOTTO",
        draw_date=date(2026, 10, 17),
        numbers=[2, 4, 6, 10, 15, 46],
        bonus_ball=1,
    )
    board = GeneratedBoard(
        id=10,
        game_type="LOTTO",
        target_draw_date=date(2026, 10, 17),
        numbers=[2, 4, 6, 20, 25, 46],
        confidence_score=85.0,
        ai_reasoning="Heavy concentration on hot low numbers.",
    )
    result = BoardResult(
        board_id=10,
        draw_id=1,
        matched_numbers=[2, 4, 6, 46],
        matched_count=4,
        matched_bonus=False,
        division="Division 4",
        prize_amount=Decimal("250.00"),
    )

    mock_payload = {
        "game_type": "LOTTO",
        "draw_date": "2026-10-17",
        "accuracy_rate": 0.67,
        "divergence_analysis": "Board correctly predicted 4 out of 6 winning numbers (2, 4, 6, 46). Diverged on middle quadrant.",
        "calibration_recommendations": [
            "Increase spread across decades 10-19.",
            "Weight modal 3:3 parity.",
        ],
    }

    with patch.object(ai_service, "call_qwen_json", return_value=mock_payload):
        feedback = await ai_service.analyze_draw_performance(draw, [board], [result])
        assert feedback.game_type == GameType.LOTTO
        assert feedback.accuracy_rate == 0.67
        assert len(feedback.calibration_recommendations) == 2


@pytest.mark.asyncio
async def test_generator_api_flow(client, db_session):
    """Verify POST /api/v1/generator/generate endpoint with circuit breaker and persistence."""
    mock_generation_response = AIGenerationResponse(
        game_type=GameType.LOTTO,
        boards=[
            AIBoardRecommendation(
                numbers=[7, 14, 21, 28, 35, 42],
                bonus_or_powerball=None,
                confidence_score=84.0,
                reasoning="Balanced distribution along statistical hot zone.",
            )
        ],
        statistical_analysis_summary="Summary of recent draws.",
    )

    with patch("app.api.v1.generator.ai_service.generate_boards", return_value=mock_generation_response):
        res = await client.post(
            "/api/v1/generator/generate",
            json={"game_type": "LOTTO", "allocated_boards": 1},
        )
        assert res.status_code == 201
        data = res.json()
        assert len(data) == 1
        assert data[0]["bundle_name"] == "LOTTO_FAMILY"
        assert data[0]["numbers"] == [7, 14, 21, 28, 35, 42]
        assert data[0]["confidence_score"] == 84.0

    # Verify quota deduction in monthly_budgets
    budget_res = await client.get("/api/v1/dashboard/budget/current")
    assert budget_res.status_code == 200
    b_data = budget_res.json()
    assert b_data["used_boards"] == 1
    assert b_data["remaining_boards"] == 19


@pytest.mark.asyncio
async def test_generator_circuit_breaker_rejection(client, db_session):
    """Directive 3: Verify POST /api/v1/generator/generate is blocked when budget is exhausted."""
    from app.budget.engine import BudgetEngine

    active_ym = BudgetEngine.current_year_month()
    # Seed budget with 0 remaining boards
    budget = MonthlyBudget(
        year_month=active_ym,
        total_budget=Decimal("200.00"),
        total_boards=20,
        used_boards=20,
        remaining_boards=0,
        is_exhausted=True,
    )
    db_session.add(budget)
    await db_session.commit()

    res = await client.post(
        "/api/v1/generator/generate",
        json={"game_type": "LOTTO", "allocated_boards": 1},
    )
    assert res.status_code == 403
    assert "Budget Exhausted" in res.json()["detail"]


@pytest.mark.asyncio
async def test_analytics_model_dispatch(ai_service):
    """Verify that temporal pattern reviews dispatch to Qwen3.8-Flash model."""
    from unittest.mock import AsyncMock
    from app.schemas.analytics import TemporalMetrics

    assert ai_service.analytics_model == "qwen3.8-flash"

    metrics = TemporalMetrics(
        sum_average=150.0,
        sum_std_dev=20.0,
        parity_ratio="3.0:3.0",
        frequency_map={"1": 3, "2": 2},
        co_occurrence_matrix={"1-2": 2},
        sample_draws_count=5,
    )

    mock_review_response = {
        "deviations": ["Short term sum deviation"],
        "momentum_shifts": ["Mid numbers trending up"],
        "hot_pairs": ["1-2"],
        "actionable_bias": {
            "suggested_sum_range": [120, 160],
            "favored_parity": "3:3",
            "boost_numbers": [1, 2],
            "dampen_numbers": [49, 50],
        },
        "summary": "Temporal variance is within standard statistical bounds.",
    }

    with patch.object(ai_service, "call_qwen_json", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = mock_review_response

        review = await ai_service.review_weekly_patterns(
            game_type=GameType.LOTTO,
            analysis_date=date(2026, 10, 22),
            weekly_metrics=metrics,
            monthly_metrics=metrics,
        )

        assert review.summary == "Temporal variance is within standard statistical bounds."
        assert review.actionable_bias.favored_parity == "3:3"
        assert mock_call.call_count == 1
        # Confirm model='qwen3.8-flash' was explicitly passed
        call_kwargs = mock_call.call_args.kwargs
        assert call_kwargs.get("model") == "qwen3.8-flash"
