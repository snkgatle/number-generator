"""FastAPI Application entrypoint with async lifespan connection management."""
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.database import check_db_connection, close_db_connection
from app.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan event context manager for startup and shutdown procedures.

    Verifies database connection pool readiness on startup and gracefully
    disposes active connection pools on application shutdown.
    """
    setup_logging()
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION} [{settings.ENVIRONMENT}]")

    # Verify Database Connection
    is_connected = await check_db_connection()
    if is_connected:
        logger.info("Database connection pool initialized and verified successfully.")
    else:
        logger.warning(
            "Database connection could not be established on startup. "
            "Async pool will retry upon incoming requests."
        )

    # Start automated background scheduler
    from app.scheduler import start_scheduler, shutdown_scheduler
    start_scheduler()

    yield

    logger.info("Application shutdown initiated. Stopping scheduler and disposing pool...")
    shutdown_scheduler()
    await close_db_connection()
    logger.info("Application shutdown complete.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Automated South African lottery analytics, scraper, and Qwen-Max generation system.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"https://.*\.appspot\.com",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Centralized exception handler to guarantee standard JSON error envelopes and CORS headers."""
    logger.error(f"Unhandled server error on {request.method} {request.url.path}: {exc}")
    headers = {}
    origin = request.headers.get("origin")
    if origin:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
        headers["Vary"] = "Origin"
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal server error occurred.",
            "error_type": exc.__class__.__name__,
        },
        headers=headers,
    )


@app.get("/", tags=["Root"])
async def root():
    """Root metadata endpoint."""
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "docs_url": "/docs",
        "api_v1": settings.API_V1_STR,
    }


# Mount API Routers
app.include_router(api_router, prefix=settings.API_V1_STR)
