"""South African National Lottery prize tier mappings and ZAR ROI evaluation.

Directive 14: Implement a static prize tier mapping for SA lotteries
to calculate actual ZAR ROI, not just match counts.
"""
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.enums import GAME_RULES, GameType


class PrizeEvaluation(BaseModel):
    """Evaluation result for an individual generated lottery board."""
    matched_numbers: List[int]
    matched_count: int
    matched_bonus: bool
    division: Optional[str]
    prize_amount: Decimal = Field(..., description="Payout in ZAR based on static prize tier mapping")
    cost_per_board: Decimal = Field(..., description="Ticket cost in ZAR (default R5.00)")
    net_yield_zar: Decimal = Field(..., description="Net yield: prize_amount - cost_per_board")
    roi_percentage: float = Field(..., description="ROI percentage: (net_yield / cost) * 100")
    is_winner: bool


class DrawROISummary(BaseModel):
    """Aggregate financial ROI across all boards in a draw."""
    total_boards: int
    total_cost_zar: Decimal
    total_winnings_zar: Decimal
    net_profit_zar: Decimal
    roi_percentage: float
    winning_boards_count: int


# ==============================================================================
# STATIC PRIZE TIER MAPPINGS (SA National Lottery Benchmark Payouts in ZAR)
# ==============================================================================

# LOTTO / LOTTO PLUS 1 / LOTTO PLUS 2 (6/52 + Bonus)
LOTTO_PRIZE_TIERS = [
    {"division": "Division 1 (Jackpot)", "match_main": 6, "match_bonus": False, "payout": Decimal("15000000.00")},
    {"division": "Division 2", "match_main": 5, "match_bonus": True, "payout": Decimal("85000.00")},
    {"division": "Division 3", "match_main": 5, "match_bonus": False, "payout": Decimal("5500.00")},
    {"division": "Division 4", "match_main": 4, "match_bonus": True, "payout": Decimal("1800.00")},
    {"division": "Division 5", "match_main": 4, "match_bonus": False, "payout": Decimal("220.00")},
    {"division": "Division 6", "match_main": 3, "match_bonus": True, "payout": Decimal("120.00")},
    {"division": "Division 7", "match_main": 3, "match_bonus": False, "payout": Decimal("50.00")},
    {"division": "Division 8", "match_main": 2, "match_bonus": True, "payout": Decimal("20.00")},
]

LOTTO_PLUS_PRIZE_TIERS = [
    {"division": "Division 1 (Jackpot)", "match_main": 6, "match_bonus": False, "payout": Decimal("3500000.00")},
    {"division": "Division 2", "match_main": 5, "match_bonus": True, "payout": Decimal("25000.00")},
    {"division": "Division 3", "match_main": 5, "match_bonus": False, "payout": Decimal("2000.00")},
    {"division": "Division 4", "match_main": 4, "match_bonus": True, "payout": Decimal("650.00")},
    {"division": "Division 5", "match_main": 4, "match_bonus": False, "payout": Decimal("100.00")},
    {"division": "Division 6", "match_main": 3, "match_bonus": True, "payout": Decimal("60.00")},
    {"division": "Division 7", "match_main": 3, "match_bonus": False, "payout": Decimal("25.00")},
    {"division": "Division 8", "match_main": 2, "match_bonus": True, "payout": Decimal("15.00")},
]

# POWERBALL / POWERBALL PLUS (5/50 + 1/16 PB)
POWERBALL_PRIZE_TIERS = [
    {"division": "Division 1 (Jackpot)", "match_main": 5, "match_bonus": True, "payout": Decimal("35000000.00")},
    {"division": "Division 2", "match_main": 5, "match_bonus": False, "payout": Decimal("180000.00")},
    {"division": "Division 3", "match_main": 4, "match_bonus": True, "payout": Decimal("9500.00")},
    {"division": "Division 4", "match_main": 4, "match_bonus": False, "payout": Decimal("1200.00")},
    {"division": "Division 5", "match_main": 3, "match_bonus": True, "payout": Decimal("400.00")},
    {"division": "Division 6", "match_main": 3, "match_bonus": False, "payout": Decimal("60.00")},
    {"division": "Division 7", "match_main": 2, "match_bonus": True, "payout": Decimal("35.00")},
    {"division": "Division 8", "match_main": 1, "match_bonus": True, "payout": Decimal("20.00")},
    {"division": "Division 9", "match_main": 0, "match_bonus": True, "payout": Decimal("10.00")},
]


class PrizeService:
    """Evaluates lottery boards against official draw results to determine ZAR prizes and ROI."""

    @staticmethod
    def get_tier_matrix(game_type: GameType) -> List[Dict[str, Any]]:
        """Returns the appropriate statutory prize tier list for the game."""
        if game_type == GameType.LOTTO:
            return LOTTO_PRIZE_TIERS
        elif game_type in (GameType.LOTTO_PLUS_1, GameType.LOTTO_PLUS_2):
            return LOTTO_PLUS_PRIZE_TIERS
        else:
            return POWERBALL_PRIZE_TIERS

    def evaluate_board(
        self,
        game_type: GameType,
        board_numbers: List[int],
        board_special: Optional[int],
        winning_numbers: List[int],
        winning_bonus: Optional[int],
        winning_powerball: Optional[int],
        cost_per_board: Decimal = Decimal("5.00"),
    ) -> PrizeEvaluation:
        """Directive 14: Calculates actual ZAR payout and net ROI for a single ticket."""
        rules = GAME_RULES.get(game_type, {})
        has_powerball = rules.get("has_powerball", False)

        # 1. Intersect main numbers
        matched_nums = sorted(set(board_numbers).intersection(set(winning_numbers)))
        matched_count = len(matched_nums)

        # 2. Check special ball match
        if has_powerball:
            # For PowerBall games, board_special is the chosen PowerBall number (1-16)
            matched_bonus = (
                board_special is not None
                and winning_powerball is not None
                and board_special == winning_powerball
            )
        else:
            # For Lotto games, bonus ball is hit if the winning bonus ball was in the board's numbers
            matched_bonus = (
                winning_bonus is not None
                and winning_bonus in board_numbers
            )

        # 3. Match against prize tier
        tier_list = self.get_tier_matrix(game_type)
        awarded_division: Optional[str] = None
        payout = Decimal("0.00")

        for tier in tier_list:
            if tier["match_main"] == matched_count and tier["match_bonus"] == matched_bonus:
                awarded_division = tier["division"]
                payout = tier["payout"]
                break

        net_yield = payout - cost_per_board
        roi = float((net_yield / cost_per_board) * 100) if cost_per_board > 0 else 0.0

        return PrizeEvaluation(
            matched_numbers=matched_nums,
            matched_count=matched_count,
            matched_bonus=matched_bonus,
            division=awarded_division,
            prize_amount=payout,
            cost_per_board=cost_per_board,
            net_yield_zar=net_yield,
            roi_percentage=round(roi, 2),
            is_winner=payout > Decimal("0.00"),
        )

    @staticmethod
    def calculate_draw_roi(
        total_boards: int,
        prize_evaluations: List[PrizeEvaluation],
        cost_per_board: Decimal = Decimal("5.00"),
    ) -> DrawROISummary:
        """Calculates macro draw ROI across a collection of board evaluations."""
        total_cost = Decimal(str(total_boards)) * cost_per_board
        total_winnings = sum((e.prize_amount for e in prize_evaluations), Decimal("0.00"))
        net_profit = total_winnings - total_cost
        roi = float((net_profit / total_cost) * 100) if total_cost > 0 else 0.0
        winners = sum(1 for e in prize_evaluations if e.is_winner)

        return DrawROISummary(
            total_boards=total_boards,
            total_cost_zar=total_cost,
            total_winnings_zar=total_winnings,
            net_profit_zar=net_profit,
            roi_percentage=round(roi, 2),
            winning_boards_count=winners,
        )
