"""Unit tests for Combinatorial Abbreviated Wheeling Service (Directive 18 & 20)."""
import pytest

from app.schemas.enums import BundleType, GameType
from app.services.wheel_service import WheelService


def test_wheel_candidate_pool_board_count_and_uniqueness():
    """Verify wheeling an N-number pool produces the exact requested board count with unique numbers."""
    wheel_svc = WheelService()
    # 10 candidate numbers
    pool = [5, 12, 19, 23, 34, 38, 42, 45, 48, 51]
    board_count = 3

    boards = wheel_svc.wheel_candidate_pool(
        pool=pool,
        board_count=board_count,
        game_type=GameType.LOTTO,
        base_confidence=85.0,
    )

    assert len(boards) == board_count

    for b in boards:
        assert len(b.numbers) == 6
        assert len(set(b.numbers)) == 6
        # Every number on each board must originate from the candidate pool
        assert all(n in pool for n in b.numbers)
        assert b.confidence_score == 85.0
        assert b.bonus_or_powerball is None


def test_wheel_candidate_pool_ev_preference():
    """Verify that wheeling avoids human-biased combinations when selecting boards."""
    wheel_svc = WheelService()
    # Pool with mix of low calendar numbers and high numbers
    pool = [3, 7, 11, 15, 19, 23, 35, 39, 44, 48, 51]

    boards = wheel_svc.wheel_candidate_pool(
        pool=pool,
        board_count=2,
        game_type=GameType.LOTTO,
    )

    assert len(boards) == 2
    # Ensure generated boards avoid pure calendar bias (not all <= 31)
    for b in boards:
        high_nums = [n for n in b.numbers if n > 31]
        assert len(high_nums) >= 1  # Guaranteed to contain high-EV numbers


def test_wheel_candidate_pool_powerball():
    """Verify wheeling sets the powerball field correctly for PowerBall games."""
    wheel_svc = WheelService()
    pool = [4, 14, 25, 33, 41, 47, 49]

    boards = wheel_svc.wheel_candidate_pool(
        pool=pool,
        board_count=2,
        game_type=GameType.POWERBALL,
        bonus_or_powerball=12,
    )

    assert len(boards) == 2
    for b in boards:
        assert len(b.numbers) == 5
        assert b.bonus_or_powerball == 12


def test_wheel_candidate_pool_padding_undersized():
    """Verify that an undersized pool (< required numbers count) is padded safely."""
    wheel_svc = WheelService()
    short_pool = [12, 19, 34]  # only 3 numbers, LOTTO requires 6

    boards = wheel_svc.wheel_candidate_pool(
        pool=short_pool,
        board_count=1,
        game_type=GameType.LOTTO,
    )

    assert len(boards) == 1
    assert len(boards[0].numbers) == 6
    # Original 3 numbers should still be present
    for n in short_pool:
        assert n in boards[0].numbers


def test_wheel_powerball_bundle_produces_valid_boards():
    """Regression: Critical #2 — POWERBALL_FAMILY bundle must wheel into 5-number boards
    with a Powerball (1-16), not 6-number boards without one.
    """
    wheel_svc = WheelService()
    pool = [4, 14, 25, 33, 41, 47, 49, 50]

    boards = wheel_svc.wheel_candidate_pool(
        pool=pool,
        board_count=2,
        game_type=BundleType.POWERBALL_FAMILY,
        bonus_or_powerball=12,
    )

    assert len(boards) == 2
    for b in boards:
        assert len(b.numbers) == 5, f"PowerBall boards must have 5 numbers, got {len(b.numbers)}"
        assert all(1 <= n <= 50 for n in b.numbers), "Numbers must be within 1-50"
        assert b.bonus_or_powerball == 12, "Powerball must be set"
        assert 1 <= b.bonus_or_powerball <= 16


def test_wheel_accepts_str_game_type():
    """Regression: Critical #2 — wheel_candidate_pool must accept plain string game_type
    (the pipeline passes bundle.value as a str).
    """
    wheel_svc = WheelService()
    pool = [4, 14, 25, 33, 41, 47, 49, 50]

    boards_str = wheel_svc.wheel_candidate_pool(
        pool=pool,
        board_count=2,
        game_type="POWERBALL_FAMILY",
        bonus_or_powerball=7,
    )
    assert len(boards_str) == 2
    for b in boards_str:
        assert len(b.numbers) == 5
        assert b.bonus_or_powerball == 7

    boards_lotto_str = wheel_svc.wheel_candidate_pool(
        pool=[5, 12, 19, 23, 34, 38, 42, 45],
        board_count=2,
        game_type="LOTTO_FAMILY",
    )
    assert len(boards_lotto_str) == 2
    for b in boards_lotto_str:
        assert len(b.numbers) == 6
        assert b.bonus_or_powerball is None
