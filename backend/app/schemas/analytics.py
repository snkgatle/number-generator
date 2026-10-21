"""Pydantic schemas for temporal analytics and Qwen pattern review validation."""
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class TemporalMetrics(BaseModel):
    """Calculated mathematical aggregates over a temporal window (7-day or 30-day)."""
    sum_average: float = Field(..., description="Average sum of winning numbers in period")
    sum_std_dev: float = Field(..., description="Standard deviation of winning sums in period")
    parity_ratio: str = Field(..., description="Average odd:even ratio (e.g., '3.1:2.9')")
    frequency_map: Dict[str, int] = Field(
        default_factory=dict,
        description="Occurrence count for each number in period",
    )
    co_occurrence_matrix: Dict[str, int] = Field(
        default_factory=dict,
        description="Top number pairs drawn together in the period (e.g., '7-14': 3)",
    )
    sample_draws_count: int = Field(..., description="Number of draws evaluated in window")


class ActionableBias(BaseModel):
    """Actionable bias recommendations to guide primary board generation."""
    suggested_sum_range: Optional[List[int]] = Field(
        None,
        description="Recommended [min_sum, max_sum] based on temporal distribution",
    )
    favored_parity: Optional[str] = Field(
        None,
        description="Favored odd:even parity ratio (e.g. '3:3' or '4:2')",
    )
    boost_numbers: List[int] = Field(
        default_factory=list,
        description="Numbers exhibiting positive momentum",
    )
    dampen_numbers: List[int] = Field(
        default_factory=list,
        description="Numbers exhibiting cold stagnation or exhaustion",
    )


class TemporalPatternReviewResponse(BaseModel):
    """Strict structured JSON response from Qwen-Max for Pattern Discovery prompts."""
    deviations: List[str] = Field(
        default_factory=list,
        description="Statistically significant deviations from monthly baseline",
    )
    momentum_shifts: List[str] = Field(
        default_factory=list,
        description="Short-term momentum movements across numbers and ranges",
    )
    hot_pairs: List[str] = Field(
        default_factory=list,
        description="Notable co-occurring pairs in the evaluated period",
    )
    actionable_bias: ActionableBias = Field(
        default_factory=ActionableBias,
        description="Structured bias to inject into primary board generation",
    )
    summary: str = Field(
        ...,
        min_length=10,
        description="Executive data scientist summary of temporal state (no fortune-telling)",
    )


class TemporalAnalyticsResponse(BaseModel):
    """API response schema for stored temporal analytics."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    game_type: str
    timeframe: str
    analysis_date: date
    sample_draws_count: int
    sum_average: float
    sum_std_dev: float
    parity_ratio: str
    frequency_map: Dict[str, int]
    co_occurrence_matrix: Dict[str, int]
    actionable_bias_for_generation: Optional[Dict[str, Any]] = None
    ai_insights: Optional[str] = None
    created_at: datetime
