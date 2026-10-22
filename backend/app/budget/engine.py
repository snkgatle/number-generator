"""Budget Engine - Confidence-based board allocation and Circuit Breaker enforcement.

Adheres strictly to:
- Directive 3: Query monthly_budgets before ANY board generation logic executes.
  If remaining_boards <= 0, halt execution and log 'Budget Exhausted'.
- Directive 23: R200 monthly initialization (20 bundled boards @ R10.00) and confidence-based allocation.
"""
import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Union
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.budget import MonthlyBudget
from app.schemas.budget import (
    AllocationPlanResponse,
    BoardAllocationRecommendation,
    CircuitBreakerStatus,
)
from app.schemas.enums import BundleType, GameType


class BudgetExhaustedException(Exception):
    """Raised when board generation is halted by the Circuit Breaker."""
    pass


class BudgetEngine:
    """Manages monthly lottery budgets, circuit breakers, and confidence-driven board allocations."""

    # Directive 23 & Phase 1.5: Raised to 90% due to higher bundle board cost (R10)
    CONFIDENCE_BONUS_THRESHOLD: float = 90.0

    @staticmethod
    def get_cycle_date_range(target_date: Optional[date] = None) -> Tuple[date, date, str]:
        """Resolves the active monthly budget cycle date range and period identifier.

        The budget cycle runs from the rollover day (default 25th) of month M
        to the day before the rollover day (24th) of month M+1.
        Returns:
            Tuple of (cycle_start_date, cycle_end_date, cycle_key_YYYY_MM).
        """
        ref_date = target_date or date.today()
        rollover_day = settings.BUDGET_CYCLE_ROLLOVER_DAY

        if ref_date.day >= rollover_day:
            # Cycle started on the rollover day of the current month
            cycle_start = date(ref_date.year, ref_date.month, rollover_day)
            if ref_date.month == 12:
                next_cycle_start = date(ref_date.year + 1, 1, rollover_day)
            else:
                next_cycle_start = date(ref_date.year, ref_date.month + 1, rollover_day)
            cycle_end = next_cycle_start - timedelta(days=1)
            cycle_key = ref_date.strftime("%Y-%m")
        else:
            # Cycle started on the rollover day of the previous month
            if ref_date.month == 1:
                cycle_start = date(ref_date.year - 1, 12, rollover_day)
            else:
                cycle_start = date(ref_date.year, ref_date.month - 1, rollover_day)
            cycle_end = date(ref_date.year, ref_date.month, rollover_day) - timedelta(days=1)
            cycle_key = cycle_start.strftime("%Y-%m")

        return cycle_start, cycle_end, cycle_key

    @classmethod
    def current_year_month(cls, target_date: Optional[date] = None) -> str:
        """Returns the YYYY-MM period key for the given date based on the 25th rollover cycle."""
        _, _, cycle_key = cls.get_cycle_date_range(target_date)
        return cycle_key

    async def get_or_create_monthly_budget(
        self, db: AsyncSession, year_month: Optional[str] = None
    ) -> MonthlyBudget:
        """Retrieves or initializes the monthly budget record for the given period.

        Initializes with default values: R200 budget, R10/board = 20 boards (Directive 23).
        """
        ym = year_month or self.current_year_month()
        query = select(MonthlyBudget).where(MonthlyBudget.year_month == ym)
        result = await db.execute(query)
        budget = result.scalar_one_or_none()

        if not budget:
            total_budget = Decimal(str(settings.DEFAULT_MONTHLY_BUDGET))
            cost_per_board = Decimal(str(settings.COST_PER_BOARD))
            total_boards = int(total_budget // cost_per_board)

            budget = MonthlyBudget(
                year_month=ym,
                total_budget=total_budget,
                cost_per_board=cost_per_board,
                total_boards=total_boards,
                remaining_boards=total_boards,
                used_boards=0,
                spent_amount=Decimal("0.00"),
                is_exhausted=False,
            )
            db.add(budget)
            await db.commit()
            await db.refresh(budget)
            logger.info(
                f"Initialized new monthly budget for {ym}: R{total_budget} ({total_boards} boards)."
            )

        return budget

    async def check_circuit_breaker(
        self, db: AsyncSession, boards_requested: int = 1, year_month: Optional[str] = None
    ) -> Tuple[bool, MonthlyBudget]:
        """Directive 3 Circuit Breaker verification.

        Before ANY board generation logic executes, query the monthly_budgets table.
        If remaining_boards <= 0, halt execution and log 'Budget Exhausted'.
        """
        budget = await self.get_or_create_monthly_budget(db, year_month=year_month)

        if budget.remaining_boards <= 0 or budget.is_exhausted:
            logger.error(
                f"Budget Exhausted: Remaining boards={budget.remaining_boards}, "
                f"is_exhausted={budget.is_exhausted} for period {budget.year_month}."
            )
            raise BudgetExhaustedException("Budget Exhausted. Board generation halted by Circuit Breaker.")

        if budget.remaining_boards < boards_requested:
            logger.warning(
                f"Circuit Breaker Warning: Requested {boards_requested} boards exceeds "
                f"remaining {budget.remaining_boards} boards for period {budget.year_month}."
            )
            return False, budget

        return True, budget

    async def get_circuit_breaker_status(
        self, db: AsyncSession, year_month: Optional[str] = None
    ) -> CircuitBreakerStatus:
        """Returns the current status of the budget circuit breaker."""
        budget = await self.get_or_create_monthly_budget(db, year_month=year_month)
        allowed = budget.remaining_boards > 0 and not budget.is_exhausted
        message = (
            "Active - board generation permitted"
            if allowed
            else "Budget Exhausted - board generation halted by Circuit Breaker"
        )
        return CircuitBreakerStatus(
            allowed=allowed,
            year_month=budget.year_month,
            remaining_boards=budget.remaining_boards,
            used_boards=budget.used_boards,
            total_boards=budget.total_boards,
            spent_amount=budget.spent_amount,
            is_exhausted=budget.is_exhausted,
            message=message,
        )

    def calculate_remaining_draws_in_month(
        self, target_date: Optional[date] = None
    ) -> Dict[str, int]:
        """Calculates total and remaining draw events in the active budget cycle across all game families.

        LOTTO variants: Wednesday (day 2) and Saturday (day 5)
        POWERBALL variants: Tuesday (day 1) and Friday (day 4)
        Active cycle: rollover day (25th) of month M to 24th of month M+1.
        """
        ref_date = target_date or date.today()
        cycle_start, cycle_end, _ = self.get_cycle_date_range(ref_date)

        lotto_draws_total = 0
        lotto_draws_remaining = 0
        powerball_draws_total = 0
        powerball_draws_remaining = 0

        current = cycle_start
        while current <= cycle_end:
            weekday = current.weekday()  # Monday=0, Tuesday=1, Wednesday=2, Friday=4, Saturday=5
            is_future_or_today = current >= ref_date

            if weekday in (2, 5):  # Wed, Sat -> LOTTO, LOTTO PLUS 1, LOTTO PLUS 2
                lotto_draws_total += 1
                if is_future_or_today:
                    lotto_draws_remaining += 1

            if weekday in (1, 4):  # Tue, Fri -> POWERBALL, POWERBALL PLUS
                powerball_draws_total += 1
                if is_future_or_today:
                    powerball_draws_remaining += 1

            current += timedelta(days=1)

        return {
            "lotto_draws_total": lotto_draws_total,
            "lotto_draws_remaining": lotto_draws_remaining,
            "powerball_draws_total": powerball_draws_total,
            "powerball_draws_remaining": powerball_draws_remaining,
            "total_draws_remaining": lotto_draws_remaining + powerball_draws_remaining,
        }

    async def calculate_confidence_allocation(
        self,
        db: AsyncSession,
        game_type: Union[GameType, BundleType, str],
        target_date: Optional[date] = None,
        confidence_score: Optional[float] = None,
    ) -> BoardAllocationRecommendation:
        """Computes board allocation for a draw based on statistical confidence and monthly quota.

        Rules:
        1. Query monthly_budgets and enforce Circuit Breaker (halt if remaining <= 0).
        2. Base allocation: 1 board per draw.
        3. Confidence Bonus: If confidence_score >= 90.0%, allocate +1 bonus board
           (provided remaining quota > total remaining draws to avoid early budget starvation).
        4. Hard cap: Total allocated boards can never exceed remaining_boards.
        """
        draw_date = target_date or date.today()
        ym = self.current_year_month(draw_date)

        # Directive 3 Circuit Breaker Check
        allowed, budget = await self.check_circuit_breaker(db, boards_requested=1, year_month=ym)

        base_boards = 1
        bonus_boards = 0
        reasoning_parts = ["Baseline allocation of 1 board assigned."]

        # Evaluate confidence bonus
        if confidence_score is not None:
            if confidence_score >= self.CONFIDENCE_BONUS_THRESHOLD:
                # Check if there is budget surplus to grant bonus board
                draws_info = self.calculate_remaining_draws_in_month(draw_date)
                remaining_draws = draws_info["total_draws_remaining"]

                # If remaining boards exceeds remaining future draws, grant bonus board
                if budget.remaining_boards > remaining_draws:
                    bonus_boards = 1
                    reasoning_parts.append(
                        f"High confidence score ({confidence_score:.1f}% >= {self.CONFIDENCE_BONUS_THRESHOLD}%) "
                        f"qualified for +1 bonus board (surplus {budget.remaining_boards - remaining_draws} available)."
                    )
                else:
                    reasoning_parts.append(
                        f"High confidence score ({confidence_score:.1f}%), but bonus withheld to preserve "
                        f"quota for remaining {remaining_draws} draws this month."
                    )
            else:
                reasoning_parts.append(
                    f"Confidence score ({confidence_score:.1f}%) below {self.CONFIDENCE_BONUS_THRESHOLD}% threshold; standard 1 board allocated."
                )

        candidate_total = base_boards + bonus_boards
        total_allocated = min(candidate_total, budget.remaining_boards)

        if total_allocated < candidate_total:
            reasoning_parts.append(
                f"Allocation capped from {candidate_total} to {total_allocated} by remaining monthly quota."
            )

        game_val = game_type.value if hasattr(game_type, "value") else str(game_type)
        return BoardAllocationRecommendation(
            game_type=game_val,
            target_draw_date=draw_date.isoformat(),
            base_boards=base_boards,
            bonus_boards=bonus_boards,
            total_allocated=total_allocated,
            confidence_score=confidence_score,
            reasoning=" ".join(reasoning_parts),
            circuit_breaker_active=budget.remaining_boards <= 0 or budget.is_exhausted,
            remaining_budget_boards=budget.remaining_boards,
        )

    async def record_board_allocation(
        self,
        db: AsyncSession,
        boards_count: int = 1,
        year_month: Optional[str] = None,
    ) -> MonthlyBudget:
        """Deducts boards from the monthly quota and persists spend.

        If remaining_boards drops to 0, sets is_exhausted = True.
        """
        _, budget = await self.check_circuit_breaker(
            db, boards_requested=boards_count, year_month=year_month
        )

        cost = budget.cost_per_board * boards_count
        budget.used_boards += boards_count
        budget.remaining_boards = max(0, budget.remaining_boards - boards_count)
        budget.spent_amount += cost

        if budget.remaining_boards == 0:
            budget.is_exhausted = True
            logger.warning(
                f"Monthly budget exhausted for period {budget.year_month}. "
                f"Circuit breaker tripped (used={budget.used_boards}, spent=R{budget.spent_amount})."
            )

        await db.commit()
        await db.refresh(budget)
        return budget

    async def get_allocation_plan(
        self, db: AsyncSession, year_month: Optional[str] = None
    ) -> AllocationPlanResponse:
        """Generates a comprehensive month overview with projected draw allocations."""
        budget = await self.get_or_create_monthly_budget(db, year_month=year_month)
        draws_info = self.calculate_remaining_draws_in_month()

        # Build sample baseline recommendation for next upcoming draws
        sample_recs = []
        for g in [GameType.LOTTO, GameType.POWERBALL]:
            rec = await self.calculate_confidence_allocation(
                db, game_type=g, target_date=date.today(), confidence_score=86.5
            )
            sample_recs.append(rec)

        return AllocationPlanResponse(
            year_month=budget.year_month,
            total_budget_zar=budget.total_budget,
            total_boards=budget.total_boards,
            used_boards=budget.used_boards,
            remaining_boards=budget.remaining_boards,
            is_exhausted=budget.is_exhausted,
            confidence_threshold=self.CONFIDENCE_BONUS_THRESHOLD,
            cost_per_board_zar=budget.cost_per_board,
            projected_draws_count=draws_info["total_draws_remaining"],
            recommendations=sample_recs,
        )
