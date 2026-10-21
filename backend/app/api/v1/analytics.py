"""FastAPI router for temporal analytics and pattern discovery."""
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.analytics import TemporalAnalytics
from app.schemas.analytics import TemporalAnalyticsResponse
from app.schemas.enums import GameType
from app.services.analytics_service import TemporalAnalyticsService

router = APIRouter(prefix="/analytics", tags=["Temporal Analytics"])
analytics_service = TemporalAnalyticsService()


@router.post(
    "/weekly",
    response_model=TemporalAnalyticsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger weekly temporal variance analysis",
)
async def trigger_weekly_analysis(
    game_type: GameType = Query(..., description="Target lottery game"),
    analysis_date: Optional[date] = Query(None, description="Reference date for analysis"),
    db: AsyncSession = Depends(get_db),
):
    """Executes a 7-day vs 30-day temporal variance review and stores Qwen pattern insights."""
    try:
        record = await analytics_service.run_weekly_analysis(db, game_type, analysis_date)
        return record
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Weekly temporal analysis failed: {str(exc)}",
        )


@router.post(
    "/monthly",
    response_model=TemporalAnalyticsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger monthly macro deep-dive",
)
async def trigger_monthly_deep_dive(
    game_type: GameType = Query(..., description="Target lottery game"),
    analysis_date: Optional[date] = Query(None, description="Reference date for analysis"),
    db: AsyncSession = Depends(get_db),
):
    """Executes monthly macro deep-dive reviewing past multi-week summaries."""
    try:
        record = await analytics_service.run_monthly_deep_dive(db, game_type, analysis_date)
        return record
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Monthly deep-dive failed: {str(exc)}",
        )


@router.get(
    "/latest/{game_type}",
    response_model=TemporalAnalyticsResponse,
    summary="Get latest temporal analytics and bias for a game",
)
async def get_latest_analytics(
    game_type: GameType,
    timeframe: Optional[str] = Query("WEEKLY", description="WEEKLY or MONTHLY"),
    db: AsyncSession = Depends(get_db),
):
    """Returns the most recent temporal analysis record and actionable bias."""
    query = (
        select(TemporalAnalytics)
        .where(
            TemporalAnalytics.game_type == game_type.value,
            TemporalAnalytics.timeframe == timeframe.upper(),
        )
        .order_by(TemporalAnalytics.analysis_date.desc(), TemporalAnalytics.id.desc())
        .limit(1)
    )
    result = await db.execute(query)
    record = result.scalars().first()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {timeframe} temporal analytics record found for {game_type.value}.",
        )
    return record


@router.get(
    "/history/{game_type}",
    response_model=List[TemporalAnalyticsResponse],
    summary="Get historical temporal analytics records",
)
async def get_analytics_history(
    game_type: GameType,
    timeframe: Optional[str] = Query(None, description="Optional filter by WEEKLY or MONTHLY"),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Lists past temporal analytics evaluations."""
    query = select(TemporalAnalytics).where(TemporalAnalytics.game_type == game_type.value)
    if timeframe:
        query = query.where(TemporalAnalytics.timeframe == timeframe.upper())

    query = query.order_by(TemporalAnalytics.analysis_date.desc(), TemporalAnalytics.id.desc()).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())
