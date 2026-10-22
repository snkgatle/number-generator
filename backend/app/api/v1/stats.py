"""Stats Router - endpoints for lottery frequency distribution and pattern metrics."""
from typing import Dict, List, Optional
from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.enums import GameType
from app.schemas.stats import (
    DeltaDistributionReport,
    EVScoreReport,
    EVScoreRequest,
    MarkovChainReport,
    PositionalFrequencyReport,
    StatisticalAnalysisResponse,
)
from app.services.stats_service import StatsService

router = APIRouter(prefix="/stats", tags=["Statistics"])
stats_service = StatsService()


@router.get("/{game_type}", response_model=StatisticalAnalysisResponse)
async def get_game_statistics(
    game_type: GameType,
    sample_size: int = Query(50, ge=5, le=200, description="Number of historical draws to analyze"),
    db: AsyncSession = Depends(get_db),
):
    """Calculates hot/cold numbers, odd/even ratios, consecutive pairs, and overdue delays."""
    return await stats_service.get_stats_for_game(
        db=db,
        game_type=game_type,
        sample_size=sample_size,
    )


@router.get("/{game_type}/prompt-context", response_model=Dict[str, str])
async def get_game_prompt_context(
    game_type: GameType,
    sample_size: int = Query(50, ge=5, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve pre-formatted statistical variables formatted for Qwen-Max prompt templates."""
    stats = await stats_service.get_stats_for_game(
        db=db,
        game_type=game_type,
        sample_size=sample_size,
    )
    draws = await stats_service.get_recent_draws(db, game_type, limit=sample_size)
    return stats_service.format_prompt_variables(stats, draws=draws)


@router.get("/{game_type}/deltas", response_model=DeltaDistributionReport)
async def get_delta_distribution(
    game_type: GameType,
    sample_size: int = Query(50, ge=5, le=200, description="Number of historical draws to analyze"),
    db: AsyncSession = Depends(get_db),
):
    """Directive 17: Delta System logic (gap analysis) across historical draws."""
    return await stats_service.get_delta_distribution(
        db=db,
        game_type=game_type,
        sample_size=sample_size,
    )


@router.get("/{game_type}/positional", response_model=PositionalFrequencyReport)
async def get_positional_frequencies(
    game_type: GameType,
    sample_size: int = Query(50, ge=5, le=200, description="Number of historical draws to analyze"),
    db: AsyncSession = Depends(get_db),
):
    """Directive 17: Positional Frequency tracking (P1-P6) with structural validity bounds."""
    return await stats_service.get_positional_frequencies(
        db=db,
        game_type=game_type,
        sample_size=sample_size,
    )


@router.get("/{game_type}/markov", response_model=MarkovChainReport)
async def get_markov_chain(
    game_type: GameType,
    sample_size: int = Query(50, ge=5, le=200, description="Number of historical draws to analyze"),
    alpha: float = Query(1.0, ge=0.1, le=10.0, description="Laplace smoothing parameter"),
    db: AsyncSession = Depends(get_db),
):
    """Directive 19: Markov chain transition matrix with Laplace smoothing."""
    return await stats_service.get_markov_chain(
        db=db,
        game_type=game_type,
        sample_size=sample_size,
        alpha=alpha,
    )


@router.post("/ev-score", response_model=EVScoreReport)
async def evaluate_expected_value(payload: EVScoreRequest):
    """Directive 20: Evaluates Expected Value (EV) and penalizes human-biased combinations."""
    return stats_service.calculate_ev_score(payload.numbers, game_type=payload.game_type)


