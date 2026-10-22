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


def test_environmental_correlations_insufficient_samples():
    """Directive 16: Verify that small sample sizes do not trigger Chi-Square tests."""
    service = StatsService()
    draws = sample_draws()  # only 3 draws
    report = service.calculate_environmental_correlations(draws, min_samples=15)
    assert report.has_significant_anomalies is False
    assert report.llm_prompt_summary is None
    assert len(report.significant_anomalies) == 0


def test_environmental_correlations_insignificant_metadata():
    """Directive 16: Guardrail prevents passing non-significant metadata (p >= 0.05) to Qwen."""
    service = StatsService()
    # Create 20 synthetic draws evenly distributed across machines
    draws = []
    machines = ["Machine Alpha", "Machine Beta"]
    for i in range(20):
        draws.append(
            Draw(
                draw_number=2000 + i,
                game_type="LOTTO",
                draw_date=date(2026, 9, 1),
                numbers=[(i % 10) + 1, (i % 10) + 11, 25, 35, 45, 50],
                machine_name=machines[i % 2],
                ball_set="Set 1",
            )
        )

    report = service.calculate_environmental_correlations(draws, min_samples=10)
    # Uniform/symmetric distribution should yield p >= 0.05
    for anomaly in report.significant_anomalies:
        assert anomaly.p_value < 0.05


def test_environmental_correlations_significant_anomaly_detection():
    """Directive 16: Validates anomaly detection when p < 0.05."""
    service = StatsService()
    draws = []
    # Machine Alpha only produces low decade balls (1-10)
    for i in range(12):
        draws.append(
            Draw(
                draw_number=3000 + i,
                game_type="LOTTO",
                draw_date=date(2026, 8, 1),
                numbers=[1, 2, 3, 4, 5, 6],
                machine_name="Alpha",
            )
        )
    # Machine Beta only produces high decade balls (41-52)
    for i in range(12):
        draws.append(
            Draw(
                draw_number=3050 + i,
                game_type="LOTTO",
                draw_date=date(2026, 8, 15),
                numbers=[44, 45, 46, 47, 48, 49],
                machine_name="Beta",
            )
        )

    report = service.calculate_environmental_correlations(draws, min_samples=15)
    assert report.has_significant_anomalies is True
    assert len(report.significant_anomalies) >= 1
    assert report.significant_anomalies[0].p_value < 0.05
    assert report.llm_prompt_summary is not None
    assert "Alpha" in report.llm_prompt_summary or "machine_name" in report.llm_prompt_summary


def test_run_monte_carlo_stress_test():
    """Directive 15: Run 10,000 Monte Carlo simulation draws with weighted probabilities."""
    service = StatsService()
    historical = sample_draws()

    proposed_boards = [
        {"numbers": [5, 12, 19, 23, 44, 51], "bonus_or_powerball": None},
        {"numbers": [1, 2, 3, 4, 6, 7], "bonus_or_powerball": None},
    ]

    results = service.run_monte_carlo_stress_test(
        boards=proposed_boards,
        historical_draws=historical,
        game_type=GameType.LOTTO,
        iterations=10000,
    )

    assert len(results) == 2
    for r in results:
        assert r.iterations == 10000
        assert 0.0 <= r.match_2_or_more_rate <= 1.0
        assert 0.0 <= r.match_3_or_more_rate <= 1.0
        assert 0.0 <= r.simulated_hit_rate <= 1.0
        assert r.stress_test_passed is True

    # Board 1 contains numbers with heavy historical weight (5, 44, 12)
    # It should have a higher simulated hit rate than board 2 (unobserved numbers)
    assert results[0].match_2_or_more_rate >= results[1].match_2_or_more_rate


@pytest.mark.asyncio
async def test_bundle_stats_and_intersection(db_session):
    """Directive 21 & 22: Verify multi-draw stats aggregation and statistical intersection."""
    from app.schemas.enums import BundleType

    # Seed draws across LOTTO, LOTTO_PLUS_1, LOTTO_PLUS_2
    # Notice: 7 and 14 appear in multiple sub-draws
    d1 = Draw(draw_number=501, game_type="LOTTO", draw_date=date(2026, 10, 14), numbers=[7, 14, 21, 28, 35, 42])
    d2 = Draw(draw_number=502, game_type="LOTTO_PLUS_1", draw_date=date(2026, 10, 14), numbers=[7, 14, 22, 29, 36, 43])
    d3 = Draw(draw_number=503, game_type="LOTTO_PLUS_2", draw_date=date(2026, 10, 14), numbers=[7, 14, 23, 30, 37, 44])
    db_session.add_all([d1, d2, d3])
    await db_session.commit()

    service = StatsService()
    bundle_data = await service.get_stats_for_bundle(db_session, BundleType.LOTTO_FAMILY, sample_size=10)

    assert bundle_data["bundle_name"] == "LOTTO_FAMILY"
    assert "aggregate_summary" in bundle_data
    assert "sub_draw_stats" in bundle_data
    assert len(bundle_data["sub_draw_stats"]) == 3
    # 7 and 14 should appear in the intersection of hot numbers
    intersection = bundle_data["statistical_intersection"]
    assert 7 in intersection
    assert 14 in intersection

    # Verify prompt formatting
    prompt_vars = service.format_bundle_prompt_variables(bundle_data)
    assert "sub_draw_breakdown" in prompt_vars
    assert "statistical_intersection" in prompt_vars
    assert "7" in prompt_vars["statistical_intersection"]
