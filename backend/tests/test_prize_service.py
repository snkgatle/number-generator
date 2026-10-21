"""Unit tests for PrizeService (Directive 14).

Tests statutory SA lottery prize tier mapping and actual ZAR ROI calculations.
"""
from decimal import Decimal
import pytest
from app.schemas.enums import GameType
from app.services.prize_service import PrizeService


@pytest.fixture
def prize_service():
    return PrizeService()


def test_lotto_jackpot_division_1(prize_service):
    """6 matching main numbers in LOTTO awards Division 1 jackpot (R15,000,000.00)."""
    eval_result = prize_service.evaluate_board(
        game_type=GameType.LOTTO,
        board_numbers=[3, 15, 22, 31, 40, 52],
        board_special=None,
        winning_numbers=[3, 15, 22, 31, 40, 52],
        winning_bonus=7,
        winning_powerball=None,
        cost_per_board=Decimal("5.00"),
    )

    assert eval_result.matched_count == 6
    assert eval_result.matched_bonus is False
    assert eval_result.division == "Division 1 (Jackpot)"
    assert eval_result.prize_amount == Decimal("15000000.00")
    assert eval_result.is_winner is True
    assert eval_result.net_yield_zar == Decimal("14999995.00")
    assert eval_result.roi_percentage > 100000.0


def test_lotto_division_2_with_bonus(prize_service):
    """5 matching main numbers + Bonus ball in LOTTO awards Division 2 (R85,000.00)."""
    eval_result = prize_service.evaluate_board(
        game_type=GameType.LOTTO,
        board_numbers=[3, 15, 22, 31, 40, 10],  # 10 is the bonus ball
        board_special=None,
        winning_numbers=[3, 15, 22, 31, 40, 52],  # 5 matched (3, 15, 22, 31, 40)
        winning_bonus=10,
        winning_powerball=None,
        cost_per_board=Decimal("5.00"),
    )

    assert eval_result.matched_count == 5
    assert eval_result.matched_bonus is True
    assert eval_result.division == "Division 2"
    assert eval_result.prize_amount == Decimal("85000.00")
    assert eval_result.is_winner is True
    assert eval_result.net_yield_zar == Decimal("84995.00")


def test_lotto_division_8_two_plus_bonus(prize_service):
    """2 main numbers + Bonus ball awards Division 8 (R20.00)."""
    eval_result = prize_service.evaluate_board(
        game_type=GameType.LOTTO,
        board_numbers=[3, 15, 1, 2, 4, 10],  # 3, 15 match main, 10 is bonus
        board_special=None,
        winning_numbers=[3, 15, 22, 31, 40, 52],
        winning_bonus=10,
        winning_powerball=None,
        cost_per_board=Decimal("5.00"),
    )

    assert eval_result.matched_count == 2
    assert eval_result.matched_bonus is True
    assert eval_result.division == "Division 8"
    assert eval_result.prize_amount == Decimal("20.00")
    assert eval_result.net_yield_zar == Decimal("15.00")
    assert eval_result.roi_percentage == 300.0  # (15 / 5) * 100


def test_lotto_loss_zero_prize(prize_service):
    """0-2 matches with no bonus awards R0.00 and -100% ROI."""
    eval_result = prize_service.evaluate_board(
        game_type=GameType.LOTTO,
        board_numbers=[1, 2, 3, 4, 5, 6],
        board_special=None,
        winning_numbers=[10, 20, 30, 40, 45, 50],
        winning_bonus=12,
        winning_powerball=None,
        cost_per_board=Decimal("5.00"),
    )

    assert eval_result.matched_count == 0
    assert eval_result.is_winner is False
    assert eval_result.division is None
    assert eval_result.prize_amount == Decimal("0.00")
    assert eval_result.net_yield_zar == Decimal("-5.00")
    assert eval_result.roi_percentage == -100.0


def test_powerball_division_1_jackpot(prize_service):
    """5 matching main numbers + PowerBall awards PowerBall Jackpot (R35,000,000.00)."""
    eval_result = prize_service.evaluate_board(
        game_type=GameType.POWERBALL,
        board_numbers=[5, 12, 19, 28, 44],
        board_special=8,
        winning_numbers=[5, 12, 19, 28, 44],
        winning_bonus=None,
        winning_powerball=8,
        cost_per_board=Decimal("5.00"),
    )

    assert eval_result.matched_count == 5
    assert eval_result.matched_bonus is True
    assert eval_result.division == "Division 1 (Jackpot)"
    assert eval_result.prize_amount == Decimal("35000000.00")
    assert eval_result.is_winner is True


def test_powerball_division_9_only_powerball(prize_service):
    """0 main numbers matched + PowerBall matched awards Division 9 (R10.00)."""
    eval_result = prize_service.evaluate_board(
        game_type=GameType.POWERBALL,
        board_numbers=[1, 2, 3, 4, 6],
        board_special=15,
        winning_numbers=[10, 20, 30, 40, 50],
        winning_bonus=None,
        winning_powerball=15,
        cost_per_board=Decimal("5.00"),
    )

    assert eval_result.matched_count == 0
    assert eval_result.matched_bonus is True
    assert eval_result.division == "Division 9"
    assert eval_result.prize_amount == Decimal("10.00")
    assert eval_result.net_yield_zar == Decimal("5.00")
    assert eval_result.roi_percentage == 100.0  # (5 / 5) * 100


def test_calculate_draw_roi_summary(prize_service):
    """Aggregate financial ROI calculations across multiple boards."""
    e1 = prize_service.evaluate_board(
        game_type=GameType.LOTTO,
        board_numbers=[3, 15, 22, 1, 2, 4],  # 3 match, no bonus -> Div 7: R50
        board_special=None,
        winning_numbers=[3, 15, 22, 31, 40, 52],
        winning_bonus=10,
        winning_powerball=None,
        cost_per_board=Decimal("5.00"),
    )
    e2 = prize_service.evaluate_board(
        game_type=GameType.LOTTO,
        board_numbers=[1, 2, 4, 8, 9, 11],  # 0 match -> R0
        board_special=None,
        winning_numbers=[3, 15, 22, 31, 40, 52],
        winning_bonus=10,
        winning_powerball=None,
        cost_per_board=Decimal("5.00"),
    )

    summary = prize_service.calculate_draw_roi(
        total_boards=2,
        prize_evaluations=[e1, e2],
        cost_per_board=Decimal("5.00"),
    )

    assert summary.total_boards == 2
    assert summary.total_cost_zar == Decimal("10.00")
    assert summary.total_winnings_zar == Decimal("50.00")
    assert summary.net_profit_zar == Decimal("40.00")
    assert summary.roi_percentage == 400.0
    assert summary.winning_boards_count == 1
