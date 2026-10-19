"""Dashboard Router - endpoints for budget status, metrics, and KPI tracking."""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import get_db
from app.models.budget import MonthlyBudget
from app.schemas.budget import MonthlyBudgetResponse, CircuitBreakerStatus
from app.services.budget_service import BudgetService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
budget_service = BudgetService()


@router.get("/budget/current", response_model=MonthlyBudgetResponse)
async def get_current_budget(db: AsyncSession = Depends(get_db)):
    """Retrieve or automatically initialize current month's budget record."""
    return await budget_service.get_or_create_monthly_budget(db)


@router.get("/circuit-breaker", response_model=CircuitBreakerStatus)
async def check_circuit_breaker(db: AsyncSession = Depends(get_db)):
    """Check whether the circuit breaker permits generating additional boards."""
    budget = await budget_service.get_or_create_monthly_budget(db)

    if budget.remaining_boards <= 0 or budget.is_exhausted:
        return CircuitBreakerStatus(
            allowed=False,
            year_month=budget.year_month,
            remaining_boards=budget.remaining_boards,
            used_boards=budget.used_boards,
            total_boards=budget.total_boards,
            spent_amount=budget.spent_amount,
            is_exhausted=True,
            message="Budget Exhausted. Generation blocked by Circuit Breaker.",
        )

    return CircuitBreakerStatus(
        allowed=True,
        year_month=budget.year_month,
        remaining_boards=budget.remaining_boards,
        used_boards=budget.used_boards,
        total_boards=budget.total_boards,
        spent_amount=budget.spent_amount,
        is_exhausted=False,
        message="Circuit breaker normal. Board generation permitted.",
    )


@router.get("/allocation-plan")
async def get_allocation_plan(
    year_month: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve month-wide confidence allocation forecast and draw schedule."""
    from app.budget.engine import BudgetEngine
    engine = BudgetEngine()
    return await engine.get_allocation_plan(db, year_month=year_month)

