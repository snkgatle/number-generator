"""Temporal Analytics Engine calculating statistical distributions and pattern discovery."""
from datetime import date, timedelta
import itertools
import math
from typing import Any, Dict, List, Optional
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import TemporalAnalytics
from app.models.draw import Draw
from app.schemas.analytics import TemporalMetrics, TemporalPatternReviewResponse
from app.schemas.enums import GameType
from app.services.ai_service import AIService


class TemporalAnalyticsService:
    """Calculates temporal metrics (weekly/monthly) and orchestrates Qwen pattern discovery."""

    def __init__(self, ai_service: Optional[AIService] = None):
        self.ai_service = ai_service or AIService()

    @staticmethod
    def calculate_window_metrics(draws: List[Draw]) -> TemporalMetrics:
        """Calculates sum average, std dev, parity drift, frequency, and co-occurrences.

        Directive 11: Pre-calculates statistical aggregates so raw historical
        arrays are never passed to the LLM.
        """
        if not draws:
            return TemporalMetrics(
                sum_average=0.0,
                sum_std_dev=0.0,
                parity_ratio="0:0",
                frequency_map={},
                co_occurrence_matrix={},
                sample_draws_count=0,
            )

        sums = []
        odds_count = 0
        evens_count = 0
        freq: Dict[str, int] = {}
        co_occur: Dict[str, int] = {}

        for draw in draws:
            nums = sorted(draw.numbers)
            s = sum(nums)
            sums.append(s)

            for n in nums:
                if n % 2 == 1:
                    odds_count += 1
                else:
                    evens_count += 1
                key = str(n)
                freq[key] = freq.get(key, 0) + 1

            # Compute co-occurrence pairs
            for a, b in itertools.combinations(nums, 2):
                pair_key = f"{min(a, b)}-{max(a, b)}"
                co_occur[pair_key] = co_occur.get(pair_key, 0) + 1

        n_draws = len(draws)
        sum_avg = sum(sums) / n_draws

        # Sample standard deviation
        if n_draws > 1:
            variance = sum((x - sum_avg) ** 2 for x in sums) / (n_draws - 1)
            sum_std = math.sqrt(variance)
        else:
            sum_std = 0.0

        avg_odds = odds_count / n_draws
        avg_evens = evens_count / n_draws
        parity_ratio = f"{avg_odds:.1f}:{avg_evens:.1f}"

        # Keep top 20 co-occurring pairs to keep matrix concise and relevant
        sorted_pairs = dict(
            sorted(co_occur.items(), key=lambda item: item[1], reverse=True)[:20]
        )

        return TemporalMetrics(
            sum_average=round(sum_avg, 2),
            sum_std_dev=round(sum_std, 2),
            parity_ratio=parity_ratio,
            frequency_map=freq,
            co_occurrence_matrix=sorted_pairs,
            sample_draws_count=n_draws,
        )

    async def get_draws_for_period(
        self,
        db: AsyncSession,
        game_type: GameType,
        days: int = 7,
        min_draws: int = 4,
        max_draws: int = 50,
        ref_date: Optional[date] = None,
    ) -> List[Draw]:
        """Fetches historical draws falling within the temporal window.

        Falls back to the most recent `min_draws` if the calendar window has sparse entries.
        """
        today = ref_date or date.today()
        start_date = today - timedelta(days=days)

        query = (
            select(Draw)
            .where(
                Draw.game_type == game_type.value,
                Draw.draw_date >= start_date,
                Draw.draw_date <= today,
            )
            .order_by(Draw.draw_date.desc(), Draw.draw_number.desc())
        )
        result = await db.execute(query)
        draws = list(result.scalars().all())

        # Graceful fallback: If calendar window has fewer draws than min_draws, fetch the latest N
        if len(draws) < min_draws:
            logger.debug(
                f"Only {len(draws)} draws found in {days}-day window for {game_type.value}. "
                f"Falling back to latest {min_draws} draws."
            )
            fallback_query = (
                select(Draw)
                .where(Draw.game_type == game_type.value)
                .order_by(Draw.draw_date.desc(), Draw.draw_number.desc())
                .limit(max(min_draws, max_draws if days > 14 else min_draws))
            )
            res = await db.execute(fallback_query)
            draws = list(res.scalars().all())

        return draws

    async def run_weekly_analysis(
        self,
        db: AsyncSession,
        game_type: GameType,
        analysis_date: Optional[date] = None,
    ) -> TemporalAnalytics:
        """Executes weekly temporal variance review against monthly baseline.

        Directive 11: Saves co-occurrence matrices, frequency maps, and actionable bias to DB.
        """
        ref_date = analysis_date or date.today()
        logger.info(f"Running weekly temporal analysis for {game_type.value} on {ref_date}")

        # 1. Fetch weekly (7 days / ~4 draws) and monthly baseline (30 days / ~16 draws)
        weekly_draws = await self.get_draws_for_period(db, game_type, days=7, min_draws=3, max_draws=6, ref_date=ref_date)
        monthly_draws = await self.get_draws_for_period(db, game_type, days=30, min_draws=10, max_draws=25, ref_date=ref_date)

        weekly_metrics = self.calculate_window_metrics(weekly_draws)
        monthly_metrics = self.calculate_window_metrics(monthly_draws)

        # 2. Query Qwen for Pattern Discovery Review
        review: TemporalPatternReviewResponse = await self.ai_service.review_weekly_patterns(
            game_type=game_type,
            analysis_date=ref_date,
            weekly_metrics=weekly_metrics,
            monthly_metrics=monthly_metrics,
        )

        # 3. Persist to temporal_analytics table
        record = TemporalAnalytics(
            game_type=game_type.value,
            timeframe="WEEKLY",
            analysis_date=ref_date,
            sample_draws_count=weekly_metrics.sample_draws_count,
            sum_average=weekly_metrics.sum_average,
            sum_std_dev=weekly_metrics.sum_std_dev,
            parity_ratio=weekly_metrics.parity_ratio,
            frequency_map=weekly_metrics.frequency_map,
            co_occurrence_matrix=weekly_metrics.co_occurrence_matrix,
            actionable_bias_for_generation=review.actionable_bias.model_dump(),
            ai_insights=review.summary,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)

        logger.info(
            f"Weekly temporal analysis saved: ID={record.id} {game_type.value} "
            f"Bias={record.actionable_bias_for_generation}"
        )
        return record

    async def run_monthly_deep_dive(
        self,
        db: AsyncSession,
        game_type: GameType,
        analysis_date: Optional[date] = None,
    ) -> TemporalAnalytics:
        """Executes monthly macro deep-dive reviewing past weekly trends."""
        ref_date = analysis_date or date.today()
        logger.info(f"Running monthly deep-dive analysis for {game_type.value} on {ref_date}")

        # Fetch recent weekly analyses from DB
        weekly_q = (
            select(TemporalAnalytics)
            .where(
                TemporalAnalytics.game_type == game_type.value,
                TemporalAnalytics.timeframe == "WEEKLY",
            )
            .order_by(TemporalAnalytics.analysis_date.desc())
            .limit(4)
        )
        weekly_records = list((await db.execute(weekly_q)).scalars().all())

        monthly_draws = await self.get_draws_for_period(db, game_type, days=30, min_draws=10, max_draws=30, ref_date=ref_date)
        monthly_metrics = self.calculate_window_metrics(monthly_draws)

        review = await self.ai_service.review_monthly_deep_dive(
            game_type=game_type,
            analysis_date=ref_date,
            weekly_records=weekly_records,
            monthly_metrics=monthly_metrics,
        )

        record = TemporalAnalytics(
            game_type=game_type.value,
            timeframe="MONTHLY",
            analysis_date=ref_date,
            sample_draws_count=monthly_metrics.sample_draws_count,
            sum_average=monthly_metrics.sum_average,
            sum_std_dev=monthly_metrics.sum_std_dev,
            parity_ratio=monthly_metrics.parity_ratio,
            frequency_map=monthly_metrics.frequency_map,
            co_occurrence_matrix=monthly_metrics.co_occurrence_matrix,
            actionable_bias_for_generation=review.actionable_bias.model_dump(),
            ai_insights=review.summary,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)

        logger.info(f"Monthly deep-dive saved: ID={record.id} {game_type.value}")
        return record

    async def get_latest_actionable_bias(
        self, db: AsyncSession, game_type: GameType
    ) -> Optional[Dict[str, Any]]:
        """Retrieves the latest actionable bias for generation injection."""
        query = (
            select(TemporalAnalytics)
            .where(
                TemporalAnalytics.game_type == game_type.value,
                TemporalAnalytics.actionable_bias_for_generation.isnot(None),
            )
            .order_by(TemporalAnalytics.analysis_date.desc(), TemporalAnalytics.id.desc())
            .limit(1)
        )
        result = await db.execute(query)
        record = result.scalars().first()
        return record.actionable_bias_for_generation if record else None
