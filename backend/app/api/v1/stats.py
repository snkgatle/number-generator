"""Stats Router - endpoints for lottery frequency distribution and pattern metrics."""
from typing import Dict
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.enums import GameType
from app.schemas.stats import StatisticalAnalysisResponse
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
    return stats_service.format_prompt_variables(stats)
