"""Budget service managing monthly expenditure, quota checks, and the Circuit Breaker.

Delegates core allocation logic to app.budget.engine.BudgetEngine (Directive 5).
"""
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.budget.engine import BudgetEngine, BudgetExhaustedException
from app.models.budget import MonthlyBudget


class BudgetService:
    """Service wrapper for BudgetEngine ensuring backwards-compatible access across API routers."""

    def __init__(self):
        self.engine = BudgetEngine()

    @staticmethod
    def current_year_month() -> str:
        return BudgetEngine.current_year_month()

    async def get_or_create_monthly_budget(
        self, db: AsyncSession, year_month: Optional[str] = None
    ) -> MonthlyBudget:
        return await self.engine.get_or_create_monthly_budget(db, year_month=year_month)

    async def verify_circuit_breaker(
        self, db: AsyncSession, boards_requested: int = 1
    ) -> Tuple[bool, MonthlyBudget]:
        return await self.engine.check_circuit_breaker(db, boards_requested=boards_requested)

    async def record_board_usage(
        self, db: AsyncSession, boards_used: int = 1
    ) -> MonthlyBudget:
        return await self.engine.record_board_allocation(db, boards_count=boards_used)


__all__ = ["BudgetService", "BudgetExhaustedException"]
