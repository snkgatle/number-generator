"""Pydantic schemas for statistical pre-processing and lottery pattern analysis."""
from datetime import date
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from app.schemas.enums import BundleType, GameType


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
    game_type: Union[GameType, BundleType, str]
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


# ==============================================================================
# Phase 3.7: Advanced Mathematical Models Schemas (Directives 17 - 20)
# ==============================================================================

class PositionalDistribution(BaseModel):
    """Distribution metrics for a specific number position (P1 - P6)."""
    position: str = Field(..., description="e.g. 'P1', 'P2', ..., 'P6'")
    mean: float
    median: float
    min_value: int
    max_value: int
    std_dev: float
    most_common_numbers: List[int] = Field(default_factory=list)


class PositionalFrequencyReport(BaseModel):
    """Directive 17: Positional Frequency tracking (P1-P6) to enforce structural validity."""
    game_type: GameType
    sample_size: int
    positions: Dict[str, PositionalDistribution]
    structural_validity_bounds: Dict[str, List[int]] = Field(
        ...,
        description="Plausible range [min_allowed, max_allowed] for each position (e.g. within 2.5 sigma)",
    )


class DeltaFrequency(BaseModel):
    """Frequency count for a specific gap delta."""
    delta: int
    count: int
    percentage: float


class DeltaDistributionReport(BaseModel):
    """Directive 17: Delta System logic (gap analysis) to mimic historical winning geometries."""
    game_type: GameType
    sample_size: int
    mean_delta: float
    median_delta: float
    std_delta: float
    min_delta: int
    max_delta: int
    top_deltas: List[DeltaFrequency] = Field(default_factory=list)
    positional_delta_means: Dict[str, float] = Field(
        default_factory=dict,
        description="Mean delta for each gap (delta_1 to delta_k)",
    )


class MarkovTransitionCandidate(BaseModel):
    """Top candidate number predicted by Markov transition matrix from previous draw."""
    number: int
    probability: float
    supporting_prior_numbers: List[int] = Field(
        default_factory=list,
        description="Numbers in the previous draw that contributed strongly to this transition",
    )


class MarkovChainReport(BaseModel):
    """Directive 19: Markov chain transition matrix with Laplace smoothing (alpha=1.0)."""
    game_type: GameType
    sample_size: int
    alpha: float = Field(default=1.0, description="Laplace smoothing factor")
    matrix_dimension: int = Field(..., description="Size of matrix (M x M where M is number pool size)")
    top_transition_candidates: List[MarkovTransitionCandidate] = Field(
        default_factory=list,
        description="Next draw candidate numbers ranked by transition probability from the latest draw",
    )
    latest_draw_numbers: List[int] = Field(default_factory=list)


class EVScoreRequest(BaseModel):
    """Payload to evaluate Expected Value (EV) and human bias for a board."""
    numbers: List[int] = Field(..., min_length=1, description="Board numbers to evaluate")
    game_type: Optional[GameType] = Field(None, description="Optional lottery game type")


class EVScoreReport(BaseModel):
    """Directive 20: Expected Value (EV) Optimization to penalize human-biased combinations."""
    numbers: List[int]
    ev_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="EV score (0 to 100). Higher scores indicate lower human bias and higher non-shared prize potential.",
    )
    is_human_biased: bool = Field(
        ...,
        description="True if board triggers severe human bias penalties (e.g. all <= 31 or arithmetic sequence)",
    )
    calendar_count: int = Field(..., description="Count of numbers <= 31 (birthday bias)")
    calendar_ratio: float = Field(..., description="Ratio of numbers <= 31")
    is_arithmetic_sequence: bool = False
    has_consecutive_run: bool = False
    penalties: List[str] = Field(default_factory=list)
    recommendation: str

