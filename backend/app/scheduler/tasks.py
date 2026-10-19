"""APScheduler configuration and background task definitions."""
import asyncio
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from app.budget.engine import BudgetEngine
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.scheduler import scheduler
from app.scheduler.pipeline import PipelineOrchestrator

pipeline_orchestrator = PipelineOrchestrator()


async def scheduled_pre_draw_task():
    """APScheduler task: Executes Pre-Draw pipeline (Stats -> AI -> Budget -> Save)."""
    logger.info("APScheduler Trigger: Running scheduled Pre-Draw automation...")
    try:
        result = await pipeline_orchestrator.execute_pre_draw_pipeline()
        logger.info(f"APScheduler Pre-Draw completed with status: {result.get('status')}")
    except Exception as exc:
        logger.error(f"Error in scheduled Pre-Draw task: {exc}", exc_info=True)


async def scheduled_post_draw_task():
    """APScheduler task: Executes Post-Draw pipeline (Scrape -> Match -> Feedback)."""
    logger.info("APScheduler Trigger: Running scheduled Post-Draw automation...")
    try:
        result = await pipeline_orchestrator.execute_post_draw_pipeline()
        logger.info(f"APScheduler Post-Draw completed: {result.get('evaluated_boards_count')} boards evaluated.")
    except Exception as exc:
        logger.error(f"Error in scheduled Post-Draw task: {exc}", exc_info=True)


async def scheduled_monthly_rollover_task():
    """APScheduler task: Initializes new monthly budget on the 25th of every month."""
    logger.info("APScheduler Trigger: Initializing new monthly budget on payday cycle (25th)...")
    try:
        engine = BudgetEngine()
        async with AsyncSessionLocal() as db:
            budget = await engine.get_or_create_monthly_budget(db)
            logger.info(f"Monthly budget ready for period {budget.year_month}: {budget.total_boards} boards.")
    except Exception as exc:
        logger.error(f"Error in scheduled monthly rollover task: {exc}", exc_info=True)


def register_scheduled_jobs():
    """Registers standard cron triggers for LottoMind automated workflows."""
    # Pre-Draw Generation: Tue, Wed, Fri, Sat at 18:00
    scheduler.add_job(
        scheduled_pre_draw_task,
        trigger=CronTrigger(day_of_week="tue,wed,fri,sat", hour=18, minute=0),
        id="lottomind_pre_draw_generation",
        name="LottoMind Pre-Draw Board Generation",
        replace_existing=True,
    )

    # Post-Draw Scraping & Feedback: Tue, Wed, Fri, Sat at 22:30
    scheduler.add_job(
        scheduled_post_draw_task,
        trigger=CronTrigger(day_of_week="tue,wed,fri,sat", hour=22, minute=30),
        id="lottomind_post_draw_evaluation",
        name="LottoMind Post-Draw Evaluation & Feedback",
        replace_existing=True,
    )

    # Monthly Rollover: 25th of every month at 00:01
    scheduler.add_job(
        scheduled_monthly_rollover_task,
        trigger=CronTrigger(day=settings.BUDGET_CYCLE_ROLLOVER_DAY, hour=0, minute=1),
        id="lottomind_monthly_budget_rollover",
        name="LottoMind Monthly Budget Rollover",
        replace_existing=True,
    )
    logger.info("Registered 3 automated APScheduler jobs (Pre-Draw, Post-Draw, Monthly Rollover).")


def start_scheduler():
    """Starts the APScheduler instance if not already running."""
    if not scheduler.running:
        register_scheduled_jobs()
        scheduler.start()
        logger.info("APScheduler started successfully.")
    else:
        logger.warning("APScheduler is already active.")


def shutdown_scheduler():
    """Gracefully terminates the APScheduler background worker."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped gracefully.")
