from fastapi import APIRouter, Depends
from app.api.v1 import scraper, generator, dashboard, stats, analytics, auth, prizes
from app.core.config import settings
from app.core.database import check_db_connection
from app.core.security import require_authenticated_user

api_router = APIRouter()

# Public Endpoints (Health & Passwordless OTP Auth)
api_router.include_router(auth.router)


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


# Protected Routers (Directive 28: Enforce 24h JWT session verification returning HTTP 401)
api_router.include_router(scraper.router, dependencies=[Depends(require_authenticated_user)])
api_router.include_router(generator.router, dependencies=[Depends(require_authenticated_user)])
api_router.include_router(dashboard.router, dependencies=[Depends(require_authenticated_user)])
api_router.include_router(stats.router, dependencies=[Depends(require_authenticated_user)])
api_router.include_router(analytics.router, dependencies=[Depends(require_authenticated_user)])
api_router.include_router(prizes.router)  # Public — prize tiers are static reference data
