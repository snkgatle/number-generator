"""Unit tests for Phase 3.7 Advanced Mathematical Models:
- Directive 17: Delta System logic & Positional Frequency tracking (P1-P6)
- Directive 19: Markov Chain with Laplace smoothing (alpha=1.0)
- Directive 20: Expected Value (EV) optimization & human-bias penalties
"""
from datetime import date
import pytest

from app.models.draw import Draw
from app.schemas.enums import GameType
from app.services.stats_service import StatsService


@pytest.fixture
def sample_draws_series():
    """Generates a sequential series of draws for transition and gap testing."""
    return [
        Draw(
            draw_number=1,
            game_type="LOTTO",
            draw_date=date(2026, 9, 1),
            numbers=[5, 12, 19, 28, 35, 48],
            bonus_ball=7,
        ),
        Draw(
            draw_number=2,
            game_type="LOTTO",
            draw_date=date(2026, 9, 5),
            numbers=[7, 14, 21, 30, 42, 50],
            bonus_ball=3,
        ),
        Draw(
            draw_number=3,
            game_type="LOTTO",
            draw_date=date(2026, 9, 8),
            numbers=[4, 18, 25, 33, 44, 49],
            bonus_ball=11,
        ),
        Draw(
            draw_number=4,
            game_type="LOTTO",
            draw_date=date(2026, 9, 12),
            numbers=[6, 15, 24, 38, 45, 52],
            bonus_ball=16,
        ),
    ]


# ==============================================================================
# Directive 17: Delta System Logic Tests
# ==============================================================================

def test_delta_distribution_calculation(sample_draws_series):
    """Verify delta gap calculation (delta_1 = n_1, delta_i = n_i - n_{i-1})."""
    svc = StatsService()
    report = svc.calculate_delta_distribution(sample_draws_series, GameType.LOTTO)

    assert report.sample_size == 4
    assert report.mean_delta > 0
    assert report.median_delta > 0
    assert report.min_delta >= 1
    assert len(report.top_deltas) > 0
    assert "delta_1" in report.positional_delta_means
    assert "delta_6" in report.positional_delta_means

    # In Draw 1: [5, 12, 19, 28, 35, 48]
    # deltas: 5, 7, 7, 9, 7, 13
    # delta 7 should appear with high frequency
    delta_vals = [d.delta for d in report.top_deltas]
    assert 7 in delta_vals


def test_delta_distribution_empty():
    """Verify delta distribution graceful fallback when draws are empty."""
    svc = StatsService()
    report = svc.calculate_delta_distribution([], GameType.LOTTO)

    assert report.sample_size == 0
    assert report.mean_delta == 8.0
    assert report.top_deltas == []


# ==============================================================================
# Directive 17: Positional Frequency Tracking (P1 - P6)
# ==============================================================================

def test_positional_frequencies_and_bounds(sample_draws_series):
    """Verify positional tracking across P1 to P6 and structural boundary calculations."""
    svc = StatsService()
    report = svc.calculate_positional_frequencies(sample_draws_series, GameType.LOTTO)

    assert report.game_type == GameType.LOTTO
    assert report.sample_size == 4
    assert len(report.positions) == 6

    # Position P1 numbers: 5, 7, 4, 6 -> mean = 5.5
    p1 = report.positions["P1"]
    assert p1.position == "P1"
    assert p1.min_value == 4
    assert p1.max_value == 7
    assert p1.mean == 5.5

    # Position P6 numbers: 48, 50, 49, 52 -> mean = 49.75
    p6 = report.positions["P6"]
    assert p6.min_value == 48
    assert p6.max_value == 52

    # Structural bounds check
    for pos_key in ["P1", "P2", "P3", "P4", "P5", "P6"]:
        bounds = report.structural_validity_bounds[pos_key]
        assert len(bounds) == 2
        assert bounds[0] <= bounds[1]
        assert bounds[0] >= 1
        assert bounds[1] <= 52


def test_validate_positional_structure():
    """Verify positional boundary validation rejects structural outliers."""
    svc = StatsService()
    bounds = {
        "P1": [1, 20],
        "P2": [8, 30],
        "P3": [15, 38],
        "P4": [22, 45],
        "P5": [30, 50],
        "P6": [38, 52],
    }

    valid_board = [4, 12, 19, 28, 36, 48]
    assert svc.validate_positional_structure(valid_board, bounds) is True

    # P1 is 35 (out of P1 bounds [1, 20])
    invalid_board = [35, 36, 38, 40, 44, 50]
    assert svc.validate_positional_structure(invalid_board, bounds) is False


# ==============================================================================
# Directive 19: Markov Chain with Laplace Smoothing (alpha=1.0)
# ==============================================================================

def test_markov_transition_laplace_smoothing(sample_draws_series):
    """Verify Laplace smoothing (alpha=1.0) prevents zero-probability transitions."""
    svc = StatsService()
    report = svc.build_markov_transition_matrix(
        sample_draws_series, GameType.LOTTO, alpha=1.0
    )

    assert report.matrix_dimension == 52
    assert report.alpha == 1.0
    assert report.sample_size == 4
    assert len(report.latest_draw_numbers) == 6
    assert len(report.top_transition_candidates) > 0

    # Ensure all predicted transition probabilities are strictly positive (> 0.0)
    for cand in report.top_transition_candidates:
        assert cand.probability > 0.0
        assert 1 <= cand.number <= 52


# ==============================================================================
# Directive 20: Expected Value (EV) Optimization
# ==============================================================================

def test_ev_score_calendar_bias_penalty():
    """Verify boards with 100% calendar numbers (<= 31) are penalized for birthday bias."""
    svc = StatsService()
    # All numbers <= 31 (e.g., birthdays: 3, 7, 12, 18, 22, 29)
    birthday_board = [3, 7, 12, 18, 22, 29]
    report = svc.calculate_ev_score(birthday_board, GameType.LOTTO)

    assert report.calendar_count == 6
    assert report.calendar_ratio == 1.0
    assert report.is_human_biased is True
    assert any("birthday bias" in p.lower() or "calendar" in p.lower() for p in report.penalties)
    assert report.ev_score < 50.0


def test_ev_score_high_non_calendar():
    """Verify boards with numbers > 31 achieve high EV scores (low human competition)."""
    svc = StatsService()
    # High numbers > 31: 14, 34, 39, 44, 48, 51 (only 1 calendar number)
    optimal_board = [14, 34, 39, 44, 48, 51]
    report = svc.calculate_ev_score(optimal_board, GameType.LOTTO)

    assert report.calendar_count == 1
    assert report.calendar_ratio < 0.35
    assert report.is_human_biased is False
    assert report.ev_score >= 80.0
    assert "non-shared jackpot" in report.recommendation.lower() or "excellent" in report.recommendation.lower()


def test_ev_score_arithmetic_sequence():
    """Verify exact arithmetic progressions are severely penalized."""
    svc = StatsService()
    # Arithmetic sequence: 5, 10, 15, 20, 25, 30 (common casual pattern)
    arithmetic_board = [5, 10, 15, 20, 25, 30]
    report = svc.calculate_ev_score(arithmetic_board, GameType.LOTTO)

    assert report.is_arithmetic_sequence is True
    assert report.is_human_biased is True
    assert any("arithmetic" in p.lower() for p in report.penalties)


def test_ev_score_consecutive_run():
    """Verify consecutive runs of 3+ numbers are flagged and penalized."""
    svc = StatsService()
    # Consecutive run: 14, 15, 16, 17
    run_board = [7, 14, 15, 16, 17, 44]
    report = svc.calculate_ev_score(run_board, GameType.LOTTO)

    assert report.has_consecutive_run is True
    assert any("consecutive" in p.lower() for p in report.penalties)
