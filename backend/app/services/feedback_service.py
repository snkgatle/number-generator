"""Persist and aggregate post-draw outcome feedback for future calibration."""
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.board import BoardResult, GeneratedBoard
from app.models.draw import Draw
from app.models.feedback import GenerationFeedback
from app.schemas.board import PostDrawFeedbackResponse
from app.schemas.feedback import FeedbackPerformanceSummary
from app.services.prompts import PERFORMANCE_FEEDBACK_CONTEXT_PROMPT


class FeedbackService:
    """Records realized draw outcomes and turns them into a rolling calibration summary."""

    async def record_feedback(
        self,
        db: AsyncSession,
        *,
        draw: Draw,
        bundle_name: str,
        boards: Sequence[GeneratedBoard],
        results: Sequence[BoardResult],
        feedback: PostDrawFeedbackResponse,
        source: str = "qwen",
    ) -> GenerationFeedback:
        """Upsert one post-draw review keyed by (bundle_name, draw_date)."""
        unique_boards = {b.id: b for b in boards if b is not None}
        total_cost = sum(
            (b.cost or Decimal("10.00") for b in unique_boards.values()),
            Decimal("0.00"),
        )
        total_winnings = sum(
            (r.prize_amount or Decimal("0.00") for r in results),
            Decimal("0.00"),
        )
        net_profit = total_winnings - total_cost
        roi_percentage = (
            float((net_profit / total_cost) * 100) if total_cost > 0 else 0.0
        )

        values = {
            "draw_id": draw.id,
            "bundle_name": bundle_name,
            "game_type": draw.game_type,
            "draw_date": draw.draw_date,
            "boards_evaluated": len(unique_boards),
            "accuracy_rate": float(feedback.accuracy_rate),
            "divergence_analysis": feedback.divergence_analysis,
            "calibration_recommendations": list(feedback.calibration_recommendations),
            "total_winnings": total_winnings,
            "total_cost": total_cost,
            "roi_percentage": round(roi_percentage, 2),
            "source": source,
        }

        dialect_name = db.get_bind().dialect.name
        if dialect_name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            stmt = pg_insert(GenerationFeedback).values(**values)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_feedback_bundle_date",
                set_={**values, "updated_at": func.now()},
            )
            await db.execute(stmt)
        elif dialect_name == "sqlite":
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert

            stmt = sqlite_insert(GenerationFeedback).values(**values)
            stmt = stmt.on_conflict_do_update(
                index_elements=["bundle_name", "draw_date"],
                set_={**values, "updated_at": func.now()},
            )
            await db.execute(stmt)
        else:
            existing = await db.execute(
                select(GenerationFeedback).where(
                    GenerationFeedback.bundle_name == bundle_name,
                    GenerationFeedback.draw_date == draw.draw_date,
                )
            )
            record = existing.scalar_one_or_none()
            if record:
                for key, value in values.items():
                    setattr(record, key, value)
            else:
                db.add(GenerationFeedback(**values))

        await db.commit()

        saved = await db.execute(
            select(GenerationFeedback).where(
                GenerationFeedback.bundle_name == bundle_name,
                GenerationFeedback.draw_date == draw.draw_date,
            )
        )
        record = saved.scalar_one()
        logger.info(
            f"Persisted performance feedback for draw #{draw.draw_number} "
            f"({bundle_name}): accuracy={record.accuracy_rate:.1%}, ROI={record.roi_percentage:+.2f}%."
        )
        return record

    async def get_recent_feedback(
        self,
        db: AsyncSession,
        bundle_name: Optional[str] = None,
        limit: int = 20,
    ) -> List[GenerationFeedback]:
        """Return recent persisted feedback, newest first."""
        query = select(GenerationFeedback).order_by(
            GenerationFeedback.draw_date.desc(), GenerationFeedback.id.desc()
        )
        if bundle_name:
            query = query.where(GenerationFeedback.bundle_name == bundle_name)
        query = query.limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_performance_summary(
        self,
        db: AsyncSession,
        bundle_name: str,
        window: Optional[int] = None,
    ) -> FeedbackPerformanceSummary:
        """Aggregate the most recent complete evaluations into a rolling summary."""
        window_size = window or settings.FEEDBACK_WINDOW_SIZE
        records = await self.get_recent_feedback(
            db, bundle_name=bundle_name, limit=window_size
        )

        if not records:
            return FeedbackPerformanceSummary(
                bundle_name=bundle_name,
                has_sufficient_data=False,
            )

        sample_count = len(records)
        total_cost = sum((r.total_cost for r in records), Decimal("0.00"))
        total_winnings = sum((r.total_winnings for r in records), Decimal("0.00"))
        net_profit = total_winnings - total_cost
        avg_accuracy = sum(r.accuracy_rate for r in records) / sample_count
        avg_roi = sum(r.roi_percentage for r in records) / sample_count

        recommendations: List[str] = []
        seen = set()
        for record in records:
            for recommendation in record.calibration_recommendations or []:
                cleaned = str(recommendation).strip()
                if cleaned and cleaned not in seen:
                    seen.add(cleaned)
                    recommendations.append(cleaned)
                if len(recommendations) >= 5:
                    break
            if len(recommendations) >= 5:
                break

        dates = [r.draw_date for r in records]
        return FeedbackPerformanceSummary(
            bundle_name=bundle_name,
            sample_count=sample_count,
            window_start=min(dates),
            window_end=max(dates),
            avg_accuracy=round(avg_accuracy, 4),
            avg_roi=round(avg_roi, 2),
            total_winnings=total_winnings,
            total_cost=total_cost,
            net_profit=net_profit,
            latest_accuracy=records[0].accuracy_rate,
            latest_roi=records[0].roi_percentage,
            recent_recommendations=recommendations,
            has_sufficient_data=sample_count >= settings.FEEDBACK_MIN_SAMPLES,
        )

    def format_prompt_context(self, summary: FeedbackPerformanceSummary) -> str:
        """Format a summary for injection into the generation prompt."""
        if not settings.FEEDBACK_PROMPT_ENABLED or summary.sample_count == 0:
            return ""

        recommendations_block = (
            "\n".join(f"  • {rec}" for rec in summary.recent_recommendations)
            if summary.recent_recommendations
            else "  • No calibration directives recorded yet."
        )
        latest_accuracy = (
            f"{summary.latest_accuracy:.1%}"
            if summary.latest_accuracy is not None
            else "n/a"
        )
        latest_roi = (
            f"{summary.latest_roi:+.2f}%"
            if summary.latest_roi is not None
            else "n/a"
        )

        return PERFORMANCE_FEEDBACK_CONTEXT_PROMPT.format(
            sample_count=summary.sample_count,
            window_start=summary.window_start,
            window_end=summary.window_end,
            avg_accuracy=summary.avg_accuracy,
            avg_roi=summary.avg_roi,
            total_cost=float(summary.total_cost),
            total_winnings=float(summary.total_winnings),
            net_profit=float(summary.net_profit),
            latest_accuracy=latest_accuracy,
            latest_roi=latest_roi,
            recommendations_block=recommendations_block,
        )
