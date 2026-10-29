"""Pydantic schemas for persisted performance feedback and aggregated outcomes."""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class GenerationFeedbackResponse(BaseModel):
    """A persisted post-draw performance review."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    draw_id: int
    bundle_name: str
    game_type: str
    draw_date: date
    boards_evaluated: int
    accuracy_rate: float = Field(..., ge=0.0, le=1.0)
    divergence_analysis: Optional[str] = None
    calibration_recommendations: List[str] = Field(default_factory=list)
    total_winnings: Decimal
    total_cost: Decimal
    roi_percentage: float
    source: str
    created_at: datetime
    updated_at: datetime


class FeedbackPerformanceSummary(BaseModel):
    """Rolling realized-outcome summary used to calibrate future generation."""

    bundle_name: str
    sample_count: int = Field(default=0, ge=0)
    window_start: Optional[date] = None
    window_end: Optional[date] = None
    avg_accuracy: float = Field(default=0.0, ge=0.0, le=1.0)
    avg_roi: float = 0.0
    total_winnings: Decimal = Decimal("0.00")
    total_cost: Decimal = Decimal("0.00")
    net_profit: Decimal = Decimal("0.00")
    latest_accuracy: Optional[float] = None
    latest_roi: Optional[float] = None
    recent_recommendations: List[str] = Field(default_factory=list)
    has_sufficient_data: bool = False
