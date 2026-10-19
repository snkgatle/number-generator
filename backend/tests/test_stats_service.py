"""Unit tests for Statistical Analyzer and StatsService."""
from datetime import date
import pytest

from app.models.draw import Draw
from app.schemas.enums import GameType
from app.services.stats_service import StatsService
from app.stats.analyzer import (
    calculate_number_frequencies,
    get_hot_numbers,
    get_cold_numbers,
    calculate_odd_even_ratios,
    calculate_consecutive_pairs,
    calculate_overdue_numbers,
    calculate_special_ball_stats,
    generate_statistical_summary,
)


def sample_draws():
    """Generates deterministic sample draws for statistical verification."""
    return [
        Draw(
            draw_number=103,
            game_type="LOTTO",
            draw_date=date(2026, 10, 15),
            numbers=[5, 12, 19, 20, 23, 44],  # pair: (19, 20), odd: 3, even: 3
            bonus_ball=7,
        ),
        Draw(
            draw_number=102,
            game_type="LOTTO",
            draw_date=date(2026, 10, 12),
            numbers=[5, 14, 19, 20, 44, 50],  # pair: (19, 20), odd: 2, even: 4
            bonus_ball=7,
        ),
        Draw(
            draw_number=101,
            game_type="LOTTO",
            draw_date=date(2026, 10, 8),
            numbers=[5, 12, 14, 30, 44, 51],  # no consecutive pairs, odd: 3, even: 3
            bonus_ball=11,
        ),
    ]


def test_calculate_number_frequencies():
    """Verify frequency calculation for numbers 1 to 52."""
    draws = sample_draws()
    freqs = calculate_number_frequencies(draws, min_num=1, max_num=52)

    assert freqs[5] == 3   # appears in all 3 draws
    assert freqs[44] == 3  # appears in all 3 draws
    assert freqs[12] == 2  # appears in draws 103, 101
    assert freqs[19] == 2  # appears in draws 103, 102
    assert freqs[20] == 2  # appears in draws 103, 102
    assert freqs[1] == 0   # never drawn


def test_get_hot_and_cold_numbers():
    """Verify top hot numbers and bottom cold numbers."""
    draws = sample_draws()
    freqs = calculate_number_frequencies(draws, min_num=1, max_num=52)

    hot = get_hot_numbers(freqs, total_draws=len(draws), top_n=5)
    assert len(hot) == 5
    # Numbers 5 and 44 both have count 3
    assert hot[0].number in (5, 44)
    assert hot[0].count == 3
    assert hot[0].percentage == 100.0

    cold = get_cold_numbers(freqs, total_draws=len(draws), bottom_n=5)
    assert len(cold) == 5
    # Numbers with 0 count
    assert cold[0].count == 0
    assert cold[0].percentage == 0.0


def test_calculate_odd_even_ratios():
    """Verify odd/even ratio calculation and modal ratio identification."""
    draws = sample_draws()
    # draw 103: [5, 19, 23] odd, [12, 20, 44] even -> 3:3
    # draw 102: [5, 19] odd, [14, 20, 44, 50] even -> 2:4
    # draw 101: [5, 51] odd, [12, 14, 30, 44] even -> 2:4
    distributions, modal = calculate_odd_even_ratios(draws)

    assert len(distributions) == 2
    assert modal == "2:4"  # appears twice (draw 102 & 101)
    assert distributions[0].ratio == "2:4"
    assert distributions[0].count == 2
    assert distributions[1].ratio == "3:3"
    assert distributions[1].count == 1


def test_calculate_consecutive_pairs():
    """Verify detection of adjacent number pairs."""
    draws = sample_draws()
    pairs = calculate_consecutive_pairs(draws, min_count=1)

    assert len(pairs) == 1
    assert pairs[0].pair == [19, 20]
    assert pairs[0].count == 2  # appeared in draws 103 and 102


def test_calculate_overdue_numbers():
    """Verify calculation of absence latency (draws since last drawn)."""
    draws = sample_draws()
    # draws order: 103 (idx 0), 102 (idx 1), 101 (idx 2)
    # Number 5 is at idx 0 (draws_since_last = 0)
    # Number 50 is at idx 1 (draws_since_last = 1)
    # Number 30 is at idx 2 (draws_since_last = 2)
    # Number 1 was never drawn -> delay = 3 (total draws)
    overdue = calculate_overdue_numbers(draws, min_num=1, max_num=52, top_n=5)

    assert len(overdue) == 5
    # The never-drawn numbers will have delay = 3
    assert overdue[0].draws_since_last == 3


def test_calculate_special_ball_stats():
    """Verify bonus ball statistics for LOTTO and powerball for POWERBALL."""
    draws = sample_draws()
    stats_lotto = calculate_special_ball_stats(draws, GameType.LOTTO)
    assert stats_lotto["type"] == "bonus_ball"
    # bonus 7 appeared twice, bonus 11 appeared once
    assert stats_lotto["hot_bonus_balls"][0]["number"] == 7
    assert stats_lotto["hot_bonus_balls"][0]["count"] == 2

    # PowerBall test draws
    pb_draws = [
        Draw(draw_number=1, game_type="POWERBALL", draw_date=date(2026, 10, 1), numbers=[1, 2, 3, 4, 5], powerball=15),
        Draw(draw_number=2, game_type="POWERBALL", draw_date=date(2026, 10, 4), numbers=[6, 7, 8, 9, 10], powerball=15),
        Draw(draw_number=3, game_type="POWERBALL", draw_date=date(2026, 10, 8), numbers=[11, 12, 13, 14, 15], powerball=8),
    ]
    stats_pb = calculate_special_ball_stats(pb_draws, GameType.POWERBALL)
    assert stats_pb["type"] == "powerball"
    assert stats_pb["hot_powerballs"][0]["number"] == 15
    assert stats_pb["hot_powerballs"][0]["count"] == 2


def test_empty_draws_handling():
    """Verify graceful handling when no draws exist in DB."""
    summary = generate_statistical_summary([], GameType.LOTTO)
    assert summary.sample_size == 0
    assert summary.hot_numbers == []
    assert summary.cold_numbers == []
    assert summary.consecutive_pairs == []
    assert summary.most_frequent_odd_even_ratio == "3:3"


def test_format_prompt_variables():
    """Verify converting statistical analysis into template substitution variables."""
    draws = sample_draws()
    summary = generate_statistical_summary(draws, GameType.LOTTO)
    service = StatsService()
    variables = service.format_prompt_variables(summary)

    assert "hot_numbers" in variables
    assert "cold_numbers" in variables
    assert "odd_even_ratio" in variables
    assert "consecutive_pairs" in variables
    assert "overdue_numbers" in variables
    assert "19-20" in variables["consecutive_pairs"]


@pytest.mark.asyncio
async def test_stats_api_router_integration(client, db_session):
    """Verify FastAPI stats router endpoints."""
    # Seed sample draws into db
    for draw in sample_draws():
        db_session.add(draw)
    await db_session.commit()

    # Query /stats/LOTTO
    res = await client.get("/api/v1/stats/LOTTO?sample_size=10")
    assert res.status_code == 200
    data = res.json()
    assert data["game_type"] == "LOTTO"
    assert data["sample_size"] == 3
    assert len(data["hot_numbers"]) == 10
    assert len(data["cold_numbers"]) == 10
    assert "llm_prompt_context" in data

    # Query /stats/LOTTO/prompt-context
    res_ctx = await client.get("/api/v1/stats/LOTTO/prompt-context")
    assert res_ctx.status_code == 200
    ctx_data = res_ctx.json()
    assert "hot_numbers" in ctx_data
    assert "cold_numbers" in ctx_data
