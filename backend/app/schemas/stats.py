"""Pydantic schemas for statistical pre-processing and lottery pattern analysis."""
from datetime import date
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.schemas.enums import GameType


class NumberFrequency(BaseModel):
    """Frequency count and appearance percentage of a number."""
    number: int
    count: int
    percentage: float = Field(..., description="Percentage of draws containing this number")


class NumberDelay(BaseModel):
    """Draw absence latency / overdue status of a number."""
    number: int
    draws_since_last: int = Field(..., description="Number of draws since this number was last drawn")


class ConsecutivePair(BaseModel):
    """Consecutive number pair (e.g. 14 & 15) that appeared together."""
    pair: List[int] = Field(..., min_length=2, max_length=2)
    count: int


class OddEvenDistribution(BaseModel):
    """Distribution metric for odd vs even numbers in a draw."""
    ratio: str = Field(..., description="Odd:Even ratio representation (e.g. '3:3', '4:2')")
    count: int
    percentage: float


class LLMPromptContext(BaseModel):
    """Pre-computed statistical variables prepared for prompt templates to save tokens."""
    hot_numbers: List[int]
    cold_numbers: List[int]
    odd_even_ratio: str
    consecutive_pairs: List[List[int]]
    overdue_numbers: List[int]


class StatisticalAnalysisResponse(BaseModel):
    """Comprehensive statistical metrics calculated locally before AI prompt synthesis."""
    game_type: GameType
    sample_size: int
    date_range_start: Optional[date] = None
    date_range_end: Optional[date] = None
    hot_numbers: List[NumberFrequency]
    cold_numbers: List[NumberFrequency]
    overdue_numbers: List[NumberDelay]
    odd_even_ratios: List[OddEvenDistribution]
    most_frequent_odd_even_ratio: str
    consecutive_pairs: List[ConsecutivePair]
    special_ball_stats: Optional[Dict[str, Any]] = None
    llm_prompt_context: LLMPromptContext


class EnvironmentalCorrelation(BaseModel):
    """Chi-Square correlation metric for draw machine, ball set, or draw time."""
    feature_name: str
    chi2_statistic: float
    p_value: float
    is_significant: bool = Field(
        ...,
        description="Directive 16: True ONLY if p_value < 0.05",
    )
    degrees_of_freedom: int
    anomaly_description: Optional[str] = None


class EnvironmentalAnalysisReport(BaseModel):
    """Guardrailed environmental metadata report ensuring p < 0.05 before LLM exposure."""
    features_analyzed: List[str]
    significant_anomalies: List[EnvironmentalCorrelation] = Field(default_factory=list)
    has_significant_anomalies: bool = False
    llm_prompt_summary: Optional[str] = Field(
        None,
        description="Directive 16: Populated ONLY with anomalies where p < 0.05",
    )


class MonteCarloSimulationResult(BaseModel):
    """Stress test results for a generated board against 10,000 weighted probabilistic draws."""
    board_index: int
    numbers: List[int]
    bonus_or_powerball: Optional[int] = None
    iterations: int = 10000
    match_2_or_more_rate: float
    match_3_or_more_rate: float
    match_4_or_more_rate: float
    simulated_hit_rate: float = Field(
        ...,
        description="Directive 15: Empirical hit rate across 10,000 weighted simulation draws",
    )
    stress_test_passed: bool = True
