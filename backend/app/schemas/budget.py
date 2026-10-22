"""Pydantic schemas for MonthlyBudget management and Circuit Breaker logic."""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class MonthlyBudgetBase(BaseModel):
    """Base fields for monthly budget records."""
    year_month: str = Field(
        ...,
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
        description="Month in YYYY-MM format (e.g. 2026-10)",
    )
    total_budget: Decimal = Field(
        default=Decimal("200.00"),
        ge=0,
        description="Total budget allocation for the month in ZAR",
    )
    cost_per_board: Decimal = Field(
        default=Decimal("10.00"),
        gt=0,
        description="Cost in ZAR per bundled lottery board",
    )
    total_boards: int = Field(
        default=20,
        ge=0,
        description="Total allowed boards based on budget / cost_per_board",
    )
    used_boards: int = Field(
        default=0,
        ge=0,
        description="Number of boards already generated this month",
    )
    remaining_boards: int = Field(
        default=20,
        ge=0,
        description="Number of boards remaining to generate",
    )
    spent_amount: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        description="Total ZAR spent so far this month",
    )
    is_exhausted: bool = Field(
        default=False,
        description="True if remaining_boards <= 0 or budget reached",
    )


class MonthlyBudgetCreate(BaseModel):
    """Payload to initialize a new monthly budget."""
    year_month: str = Field(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    total_budget: Optional[Decimal] = Decimal("200.00")
    cost_per_board: Optional[Decimal] = Decimal("5.00")


class MonthlyBudgetUpdate(BaseModel):
    """Payload to update budget parameters or increment usage."""
    used_boards: Optional[int] = None
    remaining_boards: Optional[int] = None
    spent_amount: Optional[Decimal] = None
    is_exhausted: Optional[bool] = None


class MonthlyBudgetResponse(MonthlyBudgetBase):
    """Schema returned by budget endpoints."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class CircuitBreakerStatus(BaseModel):
    """Result of querying the budget circuit breaker before board generation."""
    allowed: bool = Field(..., description="Whether board generation is permitted")
    year_month: str
    remaining_boards: int
    used_boards: int
    total_boards: int
    spent_amount: Decimal
    is_exhausted: bool
    message: str


class BoardAllocationRecommendation(BaseModel):
    """Detailed output of the confidence-based board allocation algorithm."""
    game_type: str
    target_draw_date: str
    base_boards: int = Field(default=1, description="Standard baseline allocation per draw")
    bonus_boards: int = Field(default=0, description="Bonus boards allocated when confidence > 85%")
    total_allocated: int = Field(..., description="Total boards approved for this draw")
    confidence_score: Optional[float] = Field(None, description="Statistical or model confidence percentage")
    reasoning: str
    circuit_breaker_active: bool
    remaining_budget_boards: int


class AllocationPlanResponse(BaseModel):
    """Month-wide overview of projected vs used board allocation."""
    year_month: str
    total_budget_zar: Decimal
    total_boards: int
    used_boards: int
    remaining_boards: int
    is_exhausted: bool
    confidence_threshold: float = Field(default=85.0, description="Confidence percentage required for bonus boards")
    cost_per_board_zar: Decimal
    projected_draws_count: int
    recommendations: list[BoardAllocationRecommendation] = Field(default_factory=list)
