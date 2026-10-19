"""APScheduler task orchestration package (Phase 5)."""
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

from app.scheduler.tasks import (
    pipeline_orchestrator,
    shutdown_scheduler,
    start_scheduler,
)

__all__ = [
    "scheduler",
    "start_scheduler",
    "shutdown_scheduler",
    "pipeline_orchestrator",
]
