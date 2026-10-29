"""Tests for Daily Lotto bundle parity and isolated budget pools (Directives 21-23)."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.budget.engine import BudgetEngine, BudgetExhaustedException
from app.models.board import GeneratedBoard
from app.schemas.board import AIBoardRecommendation, AIGenerationResponse
from app.schemas.enums import (
    BUNDLE_GAMES,
    BUNDLE_RULES,
    BundleType,
    GAME_DRAW_DAYS,
    GAME_RULES,
    GameType,
    budget_pool_for_bundle,
    get_next_draw_date,
)
from app.scheduler.pipeline import PipelineOrchestrator
from app.services.prize_service import PrizeService
from app.services.scraper_service import LOTTERY_GAME_CONFIG, ScraperService


def test_daily_lotto_rules_are_registered():
    assert GameType.DAILY_LOTTO in GAME_RULES
    rules = GAME_RULES[GameType.DAILY_LOTTO]
    assert rules["main_numbers_count"] == 5
    assert rules["main_number_max"] == 36
    assert rules["has_bonus"] is False
    assert rules["has_powerball"] is False
    assert rules["mc_hit_threshold"] == 2
    assert BUNDLE_RULES[BundleType.DAILY_LOTTO]["total_cost"] == 3.00
    assert BUNDLE_GAMES[BundleType.DAILY_LOTTO] == [GameType.DAILY_LOTTO]
    assert budget_pool_for_bundle(GameType.DAILY_LOTTO) == "DAILY_LOTTO"
    assert budget_pool_for_bundle(BundleType.LOTTO_FAMILY) == "BUNDLE"


def test_daily_lotto_plays_only_sun_mon_thu():
    assert GAME_DRAW_DAYS[GameType.DAILY_LOTTO] == [0, 3, 6]
    # Wednesday 2026-10-28 -> next play day is Thursday 2026-10-29
    assert get_next_draw_date(GameType.DAILY_LOTTO, date(2026, 10, 28)) == date(2026, 10, 29)
    # Thursday 2026-10-29 is itself a play day (today inclusive)
    assert get_next_draw_date(GameType.DAILY_LOTTO, date(2026, 10, 29)) == date(2026, 10, 29)
    # Saturday -> next play day is Sunday
    assert get_next_draw_date(GameType.DAILY_LOTTO, date(2026, 10, 31)) == date(2026, 11, 1)
    # Sunday is itself a play day; Monday follows
    assert get_next_draw_date(GameType.DAILY_LOTTO, date(2026, 11, 1)) == date(2026, 11, 1)
    assert get_next_draw_date(GameType.DAILY_LOTTO, date(2026, 11, 2)) == date(2026, 11, 2)


def test_daily_lotto_prize_tiers():
    tiers = PrizeService.get_tier_matrix(GameType.DAILY_LOTTO)
    assert [t["match_main"] for t in tiers] == [5, 4, 3, 2]
    assert all(t["match_bonus"] is False for t in tiers)
    result = PrizeService().evaluate_board(
        GameType.DAILY_LOTTO,
        board_numbers=[1, 2, 3, 9, 20],
        board_special=None,
        winning_numbers=[1, 2, 3, 4, 5],
        winning_bonus=None,
        winning_powerball=None,
        cost_per_board=Decimal("3.00"),
    )
    assert result.matched_count == 3
    assert result.prize_amount == Decimal("19.91")


def test_bundle_evaluation_derives_daily_lotto_defaults():
    from unittest.mock import MagicMock

    draw = MagicMock()
    draw.game_type = "DAILY_LOTTO"
    draw.numbers = [1, 2, 3, 4, 5]
    draw.bonus_ball = None
    draw.powerball = None
    draw.draw_date = date(2026, 10, 29)

    result = PrizeService().evaluate_board_against_bundle_draws(
        board_numbers=[1, 2, 3, 9, 20],
        board_special=None,
        draws=[draw],
    )
    assert result.bundle_name == "DAILY_LOTTO"
    assert result.total_cost_zar == Decimal("3.00")


def test_daily_lotto_parses_live_api_payload_shape():
    raw = {
        "gameId": 11001,
        "drawTime": "2026-10-28T19:00:00Z",
        "plusFlag": 0,
        "winPoolName": "DAILY LOTTO",
        "wagerIssue": 2783,
        "winNumList": ["5", "23", "27", "11", "33"],
        "winPoolId": 100,
    }
    parsed = ScraperService().parse_raw_draw(raw, GameType.DAILY_LOTTO)
    assert parsed.draw_number == 2783
    assert parsed.draw_date == date(2026, 10, 28)
    assert parsed.numbers == [5, 11, 23, 27, 33]
    assert parsed.bonus_ball is None
    assert parsed.powerball is None


def test_generated_board_requires_bundle_or_game():
    with pytest.raises(ValueError):
        GeneratedBoard(target_draw_date=date(2026, 10, 29), numbers=[1, 2, 3, 4, 5])


def test_daily_lotto_scraper_config_present():
    cfg = LOTTERY_GAME_CONFIG[GameType.DAILY_LOTTO]
    assert cfg["gameId"] == 11001
    assert cfg["winPoolId"] == 100
    assert cfg["plusFlag"] == 0
    assert cfg["main_count"] == 5
    assert cfg["has_bonus"] is False
    assert cfg["has_powerball"] is False


@pytest.mark.asyncio
async def test_daily_lotto_pool_is_isolated(db_session):
    engine = BudgetEngine()
    ym = "2026-10"

    bundle_budget = await engine.get_or_create_monthly_budget(db_session, year_month=ym, pool="BUNDLE")
    daily_budget = await engine.get_or_create_monthly_budget(db_session, year_month=ym, pool="DAILY_LOTTO")

    assert bundle_budget.id != daily_budget.id
    assert bundle_budget.total_boards == 20
    assert bundle_budget.cost_per_board == Decimal("10.00")
    assert daily_budget.total_budget == Decimal("50.00")
    assert daily_budget.cost_per_board == Decimal("3.00")
    assert daily_budget.total_boards == 16

    await engine.record_board_allocation(db_session, boards_count=2, year_month=ym, pool="DAILY_LOTTO")
    refreshed_bundle = await engine.get_or_create_monthly_budget(db_session, year_month=ym, pool="BUNDLE")
    refreshed_daily = await engine.get_or_create_monthly_budget(db_session, year_month=ym, pool="DAILY_LOTTO")

    assert refreshed_daily.used_boards == 2
    assert refreshed_daily.spent_amount == Decimal("6.00")
    assert refreshed_bundle.used_boards == 0


@pytest.mark.asyncio
async def test_daily_pool_exhaustion_does_not_block_bundle_pool(db_session):
    engine = BudgetEngine()
    ym = "2026-10"
    await engine.get_or_create_monthly_budget(db_session, year_month=ym, pool="BUNDLE")
    daily = await engine.get_or_create_monthly_budget(db_session, year_month=ym, pool="DAILY_LOTTO")
    await engine.record_board_allocation(
        db_session, boards_count=daily.remaining_boards, year_month=ym, pool="DAILY_LOTTO"
    )

    with pytest.raises(BudgetExhaustedException):
        await engine.check_circuit_breaker(db_session, year_month=ym, pool="DAILY_LOTTO")

    allowed, bundle = await engine.check_circuit_breaker(db_session, year_month=ym, pool="BUNDLE")
    assert allowed is True
    assert bundle.remaining_boards == 20


@pytest.mark.asyncio
async def test_pre_draw_pipeline_generates_daily_lotto_bundle(db_session):
    orchestrator = PipelineOrchestrator()
    mock_ai_resp = AIGenerationResponse(
        game_type=GameType.DAILY_LOTTO,
        boards=[
            AIBoardRecommendation(
                numbers=[3, 11, 17, 24, 35],
                bonus_or_powerball=None,
                confidence_score=81.0,
                reasoning="Daily Lotto structural test board.",
            )
        ],
        statistical_analysis_summary="Summary",
    )

    with patch.object(orchestrator.ai_service, "generate_boards", return_value=mock_ai_resp):
        result = await orchestrator.execute_pre_draw_pipeline(
            game_types=[GameType.DAILY_LOTTO], target_date=date(2026, 10, 29), db=db_session
        )

    assert result["status"] == "COMPLETED"
    assert result["generated_boards_count"] == 1
    assert result["remaining_by_pool"]["DAILY_LOTTO"] == 15

    boards = (
        await db_session.execute(
            select(GeneratedBoard).where(GeneratedBoard.bundle_name == "DAILY_LOTTO")
        )
    ).scalars().all()
    assert len(boards) == 1
    assert boards[0].numbers == [3, 11, 17, 24, 35]
    assert boards[0].cost == Decimal("3.00")
