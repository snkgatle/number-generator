"""Statistical pre-processing service integrating mathematical pattern analysis with database draws."""
from typing import Dict, List, Optional
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.draw import Draw
from app.schemas.enums import GameType
from app.schemas.stats import StatisticalAnalysisResponse
from app.stats.analyzer import generate_statistical_summary


class StatsService:
    """Orchestrates historical draw extraction and mathematical pre-processing."""

    async def get_recent_draws(
        self, db: AsyncSession, game_type: GameType, limit: int = 50
    ) -> List[Draw]:
        """Queries the database for the last N official draws for a specific game."""
        query = (
            select(Draw)
            .where(Draw.game_type == game_type.value)
            .order_by(Draw.draw_date.desc(), Draw.draw_number.desc())
            .limit(limit)
        )
        result = await db.execute(query)
        draws = list(result.scalars().all())
        logger.debug(f"Retrieved {len(draws)} historical draws for {game_type.value} analysis.")
        return draws

    async def get_stats_for_game(
        self, db: AsyncSession, game_type: GameType, sample_size: int = 50
    ) -> StatisticalAnalysisResponse:
        """Fetches the latest draws and computes statistical summary locally."""
        draws = await self.get_recent_draws(db, game_type, limit=sample_size)
        return generate_statistical_summary(draws, game_type)

    def format_prompt_variables(
        self, stats: StatisticalAnalysisResponse
    ) -> Dict[str, str]:
        """Converts statistical analysis into formatted strings for Qwen-Max prompt templates."""
        ctx = stats.llm_prompt_context

        # Hot numbers as string
        hot_str = ", ".join(str(n) for n in ctx.hot_numbers) if ctx.hot_numbers else "None"

        # Cold numbers as string
        cold_str = ", ".join(str(n) for n in ctx.cold_numbers) if ctx.cold_numbers else "None"

        # Overdue numbers as string
        overdue_str = ", ".join(str(n) for n in ctx.overdue_numbers) if ctx.overdue_numbers else "None"

        # Consecutive pairs formatted
        pairs_str = (
            ", ".join(f"{p[0]}-{p[1]}" for p in ctx.consecutive_pairs)
            if ctx.consecutive_pairs
            else "None detected"
        )

        return {
            "hot_numbers": hot_str,
            "cold_numbers": cold_str,
            "odd_even_ratio": ctx.odd_even_ratio,
            "consecutive_pairs": pairs_str,
            "overdue_numbers": overdue_str,
        }
