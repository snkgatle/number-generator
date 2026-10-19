"""Aggregate v1 API router."""
from fastapi import APIRouter
from app.api.v1 import scraper, generator, dashboard, stats
from app.core.config import settings
from app.core.database import check_db_connection

api_router = APIRouter()


@api_router.get("/health", tags=["Health"])
async def health_check():
    """System health check endpoint verifying database connectivity."""
    db_connected = await check_db_connection()
    return {
        "status": "ok" if db_connected else "degraded",
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "database": "connected" if db_connected else "disconnected",
    }


api_router.include_router(scraper.router)
api_router.include_router(generator.router)
api_router.include_router(dashboard.router)
api_router.include_router(stats.router)
