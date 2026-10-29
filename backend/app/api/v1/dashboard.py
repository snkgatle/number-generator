"""Dashboard Router - endpoints for budget status, metrics, and KPI tracking."""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import get_db
from app.budget.engine import BudgetEngine
from app.models.budget import MonthlyBudget
from app.schemas.budget import MonthlyBudgetResponse, CircuitBreakerStatus
from app.services.budget_service import BudgetService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
budget_service = BudgetService()
budget_engine = BudgetEngine()
BUDGET_POOLS = ("BUNDLE", "DAILY_LOTTO")


@router.get("/budget/current", response_model=MonthlyBudgetResponse)
async def get_current_budget(
    pool: str = Query("BUNDLE", description="Budget pool: BUNDLE or DAILY_LOTTO"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve or automatically initialize current month's budget record for a pool."""
    return await budget_service.get_or_create_monthly_budget(db, pool=pool)


@router.get("/budgets", response_model=List[MonthlyBudgetResponse])
async def get_all_budgets(db: AsyncSession = Depends(get_db)):
    """Return the current month's budget for every active pool."""
    return [
        await budget_service.get_or_create_monthly_budget(db, pool=pool)
        for pool in BUDGET_POOLS
    ]


@router.get("/circuit-breaker", response_model=CircuitBreakerStatus)
async def check_circuit_breaker(
    pool: str = Query("BUNDLE", description="Budget pool: BUNDLE or DAILY_LOTTO"),
    db: AsyncSession = Depends(get_db),
):
    """Check whether the circuit breaker permits generating additional boards for a pool."""
    return await budget_engine.get_circuit_breaker_status(db, pool=pool)


@router.get("/allocation-plan")
async def get_allocation_plan(
    year_month: Optional[str] = None,
    pool: str = Query("BUNDLE", description="Budget pool: BUNDLE or DAILY_LOTTO"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve month-wide confidence allocation forecast and draw schedule for a pool."""
    return await budget_engine.get_allocation_plan(db, year_month=year_month, pool=pool)

