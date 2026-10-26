"""Unit and integration tests for TemporalAnalyticsService, Qwen pattern review, and endpoints."""
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.analytics import TemporalAnalytics
from app.models.draw import Draw
from app.schemas.analytics import (
    ActionableBias,
    TemporalMetrics,
    TemporalPatternReviewResponse,
)
from app.schemas.enums import BundleType, GameType
from app.services.ai_service import AIService
from app.services.analytics_service import TemporalAnalyticsService


@pytest.fixture
def sample_draws():
    """Generates a synthetic sequence of draws for statistical variance tests."""
    draws = []
    base_date = date(2026, 10, 20)
    # 6 draws with controlled numbers
    draw_data = [
        [4, 12, 19, 23, 44, 51],  # sum=153, 3 odd, 3 even
        [8, 14, 27, 33, 45, 52],  # sum=179, 3 odd, 3 even
        [4, 12, 18, 24, 30, 40],  # sum=128, 0 odd, 6 even
        [1, 3, 5, 7, 9, 11],      # sum=36,  6 odd, 0 even
        [4, 12, 19, 23, 33, 45],  # sum=136, 4 odd, 2 even
    ]
    for idx, nums in enumerate(draw_data):
        draws.append(
            Draw(
                draw_number=1000 + idx,
                game_type=GameType.LOTTO.value,
                draw_date=base_date - timedelta(days=idx * 2),
                numbers=nums,
                bonus_ball=7,
            )
        )
    return draws


def test_calculate_window_metrics_empty():
    """Verify metrics calculation returns safe zeroes on empty draws list."""
    metrics = TemporalAnalyticsService.calculate_window_metrics([])
    assert metrics.sum_average == 0.0
    assert metrics.sum_std_dev == 0.0
    assert metrics.sample_draws_count == 0
    assert metrics.frequency_map == {}
    assert metrics.co_occurrence_matrix == {}


def test_calculate_window_metrics(sample_draws):
    """Directive 11: Verify sum average, std dev, parity drift, and co-occurrences."""
    metrics = TemporalAnalyticsService.calculate_window_metrics(sample_draws)

    assert metrics.sample_draws_count == 5
    # Sums: 153, 179, 128, 36, 136 -> total = 632 / 5 = 126.4
    assert metrics.sum_average == 126.4
    assert metrics.sum_std_dev > 0.0

    # Number 4 and 12 appeared in 3 of the 5 draws
    assert metrics.frequency_map["4"] == 3
    assert metrics.frequency_map["12"] == 3

    # Co-occurrence pair 4-12 should be recorded
    assert metrics.co_occurrence_matrix.get("4-12") == 3


@pytest.mark.asyncio
async def test_run_weekly_analysis(db_session, sample_draws):
    """Verify weekly temporal analysis execution, Qwen call, and persistence."""
    for d in sample_draws:
        db_session.add(d)
    await db_session.commit()

    mock_review = TemporalPatternReviewResponse(
        deviations=["Significant parity drift in draw #1003."],
        momentum_shifts=["Numbers 4 and 12 show high weekly clustering."],
        hot_pairs=["4-12"],
        actionable_bias=ActionableBias(
            suggested_sum_range=[130, 165],
            favored_parity="3:3",
            boost_numbers=[4, 12, 19],
            dampen_numbers=[1, 9],
        ),
        summary="Weekly distribution reflects standard mean reversion around median sums.",
    )

    ai_service = AIService(api_key="mock_key")
    with patch.object(ai_service, "call_qwen_json", return_value=mock_review.model_dump()):
        analytics_service = TemporalAnalyticsService(ai_service)
        record = await analytics_service.run_weekly_analysis(
            db_session, GameType.LOTTO, analysis_date=date(2026, 10, 21)
        )

        assert record.id is not None
        assert record.game_type == "LOTTO"
        assert record.timeframe == "WEEKLY"
        assert record.sample_draws_count >= 3
        assert record.actionable_bias_for_generation["suggested_sum_range"] == [130, 165]
        assert "mean reversion" in record.ai_insights


@pytest.mark.asyncio
async def test_get_latest_actionable_bias(db_session):
    """Verify retrieval of latest actionable bias for prompt injection."""
    analytics_service = TemporalAnalyticsService()

    # Pre-populate two temporal records
    rec1 = TemporalAnalytics(
        game_type="POWERBALL",
        timeframe="WEEKLY",
        analysis_date=date(2026, 10, 10),
        sample_draws_count=4,
        sum_average=130.0,
        sum_std_dev=12.0,
        parity_ratio="3:2",
        frequency_map={},
        co_occurrence_matrix={},
        actionable_bias_for_generation={"favored_parity": "3:2", "boost_numbers": [10]},
        ai_insights="Older analysis.",
    )
    rec2 = TemporalAnalytics(
        game_type="POWERBALL",
        timeframe="WEEKLY",
        analysis_date=date(2026, 10, 17),
        sample_draws_count=4,
        sum_average=145.0,
        sum_std_dev=14.0,
        parity_ratio="2:3",
        frequency_map={},
        co_occurrence_matrix={},
        actionable_bias_for_generation={"favored_parity": "2:3", "boost_numbers": [15, 22]},
        ai_insights="Newer analysis.",
    )
    db_session.add_all([rec1, rec2])
    await db_session.commit()

    bias = await analytics_service.get_latest_actionable_bias(db_session, GameType.POWERBALL)
    assert bias is not None
    assert bias["favored_parity"] == "2:3"
    assert bias["boost_numbers"] == [15, 22]


@pytest.mark.asyncio
async def test_board_generation_with_temporal_bias():
    """Verify that temporal bias is properly formatted into the AI prompt."""
    ai_service = AIService(api_key="mock_key")

    mock_boards = {
        "game_type": "LOTTO",
        "boards": [
            {
                "numbers": [4, 12, 19, 23, 44, 51],
                "bonus_or_powerball": None,
                "confidence_score": 88.0,
                "reasoning": "Consistent with weekly positive momentum.",
            }
        ],
        "statistical_analysis_summary": "Incorporated weekly bias.",
    }

    captured_prompt = None

    async def mock_call(messages, temperature=0.7):
        nonlocal captured_prompt
        captured_prompt = messages[1]["content"]
        return mock_boards

    with patch.object(ai_service, "call_qwen_json", side_effect=mock_call):
        res = await ai_service.generate_boards(
            game_type=GameType.LOTTO,
            target_draw_date=date(2026, 10, 22),
            allocated_boards=1,
            stats_context={
                "hot_numbers": "4, 12",
                "cold_numbers": "1, 2",
                "odd_even_ratio": "3:3",
                "consecutive_pairs": "None",
                "overdue_numbers": "19",
            },
            temporal_bias={
                "suggested_sum_range": [140, 170],
                "favored_parity": "4:2",
                "boost_numbers": [4, 12, 19],
                "dampen_numbers": [1, 2],
            },
        )

        assert res.game_type == GameType.LOTTO
        assert captured_prompt is not None
        assert "Temporal Analytics Bias (Weekly/Monthly Insights):" in captured_prompt
        assert "Suggested Sum Range: 140 - 170" in captured_prompt
        assert "Favored Parity Ratio: 4:2" in captured_prompt
        assert "Momentum Boost Numbers: 4, 12, 19" in captured_prompt


@pytest.mark.asyncio
async def test_analytics_api_endpoints(client, db_session, sample_draws):
    """Verify FastAPI router endpoints for temporal analytics."""
    for d in sample_draws:
        db_session.add(d)
    await db_session.commit()

    record = TemporalAnalytics(
        game_type="LOTTO",
        timeframe="WEEKLY",
        analysis_date=date(2026, 10, 20),
        sample_draws_count=5,
        sum_average=126.4,
        sum_std_dev=18.5,
        parity_ratio="3.2:2.8",
        frequency_map={"4": 3, "12": 3},
        co_occurrence_matrix={"4-12": 3},
        actionable_bias_for_generation={"favored_parity": "3:3"},
        ai_insights="Equilibrium state.",
    )
    db_session.add(record)
    await db_session.commit()

    # 1. GET latest
    resp = await client.get("/api/v1/analytics/latest/LOTTO")
    assert resp.status_code == 200
    data = resp.json()
    assert data["game_type"] == "LOTTO"
    assert data["timeframe"] == "WEEKLY"
    assert data["sum_average"] == 126.4

    # 2. GET history
    hist_resp = await client.get("/api/v1/analytics/history/LOTTO")
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()
    assert len(hist_data) >= 1
    assert hist_data[0]["game_type"] == "LOTTO"


@pytest.mark.asyncio
async def test_get_latest_actionable_bias_resolves_bundle_key(db_session):
    """High #4: get_latest_actionable_bias must search across all member
    sub-games when queried with a bundle key, not just exact-match the key.
    """
    service = TemporalAnalyticsService()

    # Insert bias records under sub-game keys (as run_weekly_analysis does)
    from app.models.analytics import TemporalAnalytics
    from app.schemas.analytics import ActionableBias

    bias = ActionableBias(
        suggested_sum_range=[120, 160],
        favored_parity="3:3",
        boost_numbers=[7, 14],
        dampen_numbers=[50, 51],
    )

    lotto_record = TemporalAnalytics(
        game_type="LOTTO",
        timeframe="WEEKLY",
        analysis_date=date.today(),
        sample_draws_count=4,
        sum_average=130.0,
        sum_std_dev=10.0,
        parity_ratio="3:3",
        actionable_bias_for_generation=bias.model_dump(),
        ai_insights="Test bias for LOTTO sub-game.",
    )
    db_session.add(lotto_record)
    await db_session.commit()

    # Query with bundle key — must find the sub-game record
    result = await service.get_latest_actionable_bias(
        db_session, BundleType.LOTTO_FAMILY
    )
    assert result is not None
    assert result["boost_numbers"] == [7, 14]
    assert result["suggested_sum_range"] == [120, 160]

    # Query with a str bundle key too
    result_str = await service.get_latest_actionable_bias(
        db_session, "LOTTO_FAMILY"
    )
    assert result_str is not None
    assert result_str["favored_parity"] == "3:3"
