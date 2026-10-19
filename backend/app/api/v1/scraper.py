"""Scraper Router - endpoints for triggering and retrieving lottery draw data."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.draw import Draw
from app.schemas.draw import (
    DrawResponse,
    ScrapeGameResult,
    ScrapeRequest,
    ScrapeResponse,
)
from app.schemas.enums import GameType
from app.services.scraper_service import ScraperService

router = APIRouter(prefix="/scraper", tags=["Scraper"])
scraper_service = ScraperService()


@router.get("/draws", response_model=List[DrawResponse])
async def get_draws(
    game_type: Optional[GameType] = Query(None, description="Filter by lottery game type"),
    limit: int = Query(50, ge=1, le=200, description="Number of historical draws to return"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve historical lottery draws sorted by draw date descending."""
    query = select(Draw).order_by(Draw.draw_date.desc(), Draw.draw_number.desc()).limit(limit)
    if game_type:
        query = query.where(Draw.game_type == game_type.value)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/draws/{game_type}/latest", response_model=DrawResponse)
async def get_latest_draw(
    game_type: GameType,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the most recent draw for a specific game type."""
    query = (
        select(Draw)
        .where(Draw.game_type == game_type.value)
        .order_by(Draw.draw_date.desc(), Draw.draw_number.desc())
        .limit(1)
    )
    result = await db.execute(query)
    draw = result.scalar_one_or_none()
    if not draw:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No draw records found for {game_type.value}",
        )
    return draw


@router.post("/scrape", response_model=ScrapeResponse)
async def trigger_full_scrape(
    payload: Optional[ScrapeRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """Manual trigger to execute the Playwright scraping engine across all configured games."""
    request_data = payload or ScrapeRequest()
    return await scraper_service.scrape_all(
        db=db,
        game_types=request_data.game_types,
        limit=request_data.limit,
    )


@router.post("/scrape/{game_type}", response_model=ScrapeGameResult)
async def trigger_game_scrape(
    game_type: GameType,
    limit: int = Query(50, ge=1, le=100, description="Draws to fetch"),
    db: AsyncSession = Depends(get_db),
):
    """Manual trigger to scrape a single game type."""
    return await scraper_service.scrape_and_sync_game(
        db=db,
        game_type=game_type,
        limit=limit,
    )
