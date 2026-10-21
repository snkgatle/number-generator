"""Automated pipeline orchestrating Scraper -> Stats -> AI -> Budget -> Save -> Feedback.

Adheres strictly to:
- Directive 3: Budget Circuit Breaker check before board generation.
- Directive 4: Idempotent scraping (ON CONFLICT DO NOTHING).
- Directive 5: Separation of Concerns (scraper, stats, ai, budget).
- Directive 6: Tenacity retries and graceful fallback.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.budget.engine import BudgetEngine, BudgetExhaustedException
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.board import BoardResult, GeneratedBoard
from app.models.draw import Draw
from app.schemas.enums import BoardStatus, GameType
from app.services.ai_service import AIService, AIServiceError
from app.services.analytics_service import TemporalAnalyticsService
from app.services.dedup_service import DedupService
from app.services.notifier import Notifier
from app.services.prize_service import PrizeService
from app.services.scraper_service import ScraperService
from app.services.stats_service import StatsService

SCHEDULED_GAMES_BY_WEEKDAY = {
    1: [GameType.POWERBALL, GameType.POWERBALL_PLUS],             # Tuesday
    2: [GameType.LOTTO, GameType.LOTTO_PLUS_1, GameType.LOTTO_PLUS_2],  # Wednesday
    4: [GameType.POWERBALL, GameType.POWERBALL_PLUS],             # Friday
    5: [GameType.LOTTO, GameType.LOTTO_PLUS_1, GameType.LOTTO_PLUS_2],  # Saturday
}


class PipelineOrchestrator:
    """Coordinates end-to-end execution of LottoMind automated lottery operations."""

    def __init__(self, session_factory=None):
        self.session_factory = session_factory or AsyncSessionLocal
        self.budget_engine = BudgetEngine()
        self.stats_service = StatsService()
        self.ai_service = AIService()
        self.scraper_service = ScraperService()
        self.analytics_service = TemporalAnalyticsService(self.ai_service)
        self.dedup_service = DedupService()
        self.prize_service = PrizeService()
        self.notifier = Notifier()

    @staticmethod
    def get_scheduled_games_for_date(ref_date: Optional[date] = None) -> List[GameType]:
        """Identifies which lottery games have draws on the specified date."""
        d = ref_date or date.today()
        weekday = d.weekday()
        return SCHEDULED_GAMES_BY_WEEKDAY.get(weekday, [])

    async def execute_pre_draw_pipeline(
        self,
        game_types: Optional[List[GameType]] = None,
        target_date: Optional[date] = None,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """Runs the automated Pre-Draw Pipeline (Stats -> AI -> Budget -> Save).

        Directive 3: Halts with 'Budget Exhausted' if remaining boards <= 0.
        """
        if db is not None:
            return await self._run_pre_draw(db, game_types, target_date)
        async with self.session_factory() as session:
            return await self._run_pre_draw(session, game_types, target_date)

    async def _run_pre_draw(
        self,
        db: AsyncSession,
        game_types: Optional[List[GameType]] = None,
        target_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        ref_date = target_date or date.today()
        games = game_types or self.get_scheduled_games_for_date(ref_date)

        if not games:
            logger.info(f"No lottery draws scheduled for {ref_date} (weekday={ref_date.weekday()}).")
            return {
                "status": "SKIPPED",
                "message": f"No draws scheduled for {ref_date}.",
                "generated_boards_count": 0,
            }

        logger.info(f"Starting Pre-Draw Pipeline for {len(games)} games on {ref_date}: {[g.value for g in games]}")

        total_generated = 0
        results_by_game = {}

        # 1. Directive 3 Circuit Breaker Check
        try:
            allowed, budget = await self.budget_engine.check_circuit_breaker(db, boards_requested=1)
        except BudgetExhaustedException as exc:
            logger.error(f"Pre-Draw Pipeline HALTED: {exc}")
            await self.notifier.notify_budget_exhaustion(
                year_month=ref_date.strftime("%Y-%m"),
                remaining_boards=0,
                total_budget=str(settings.DEFAULT_MONTHLY_BUDGET),
            )
            return {
                "status": "HALTED",
                "reason": "Budget Exhausted",
                "remaining_boards": 0,
                "generated_boards_count": 0,
            }

        # 2. Iterate each scheduled game
        for game in games:
            if budget.remaining_boards <= 0:
                logger.warning("Monthly budget exhausted mid-pipeline. Halting subsequent games.")
                break

            logger.info(f"Processing pre-draw analysis for {game.value}...")

            # Statistical Pre-Processing (Phase 3)
            stats = await self.stats_service.get_stats_for_game(db, game, sample_size=50)
            stats_vars = self.stats_service.format_prompt_variables(stats)

            # Determine board allocation using confidence engine (Phase 5)
            allocation = await self.budget_engine.calculate_confidence_allocation(
                db, game_type=game, target_date=ref_date
            )
            boards_to_generate = allocation.total_allocated

            if boards_to_generate <= 0:
                logger.info(f"Allocation for {game.value} is 0 boards. Skipping.")
                continue

            recent_draws = await self.stats_service.get_recent_draws(db, game, limit=50)

            # Directive 16: Check environmental correlations with Chi-Square (p < 0.05 only)
            env_report = self.stats_service.calculate_environmental_correlations(recent_draws)
            env_anomalies = env_report.llm_prompt_summary if env_report.has_significant_anomalies else None

            # Directive 11: Fetch actionable temporal bias if available
            temporal_bias = await self.analytics_service.get_latest_actionable_bias(db, game)

            # Generate Boards via Qwen-Max (Phase 4, 3.5, 3.6) with Monte Carlo stress test
            try:
                ai_response = await self.ai_service.generate_boards(
                    game_type=game,
                    target_draw_date=ref_date,
                    allocated_boards=boards_to_generate,
                    stats_context=stats_vars,
                    temporal_bias=temporal_bias,
                    environmental_anomalies=env_anomalies,
                    historical_draws=recent_draws,
                )
            except AIServiceError as err:
                logger.error(f"AI generation failed for {game.value}: {err}. Skipping game.")
                results_by_game[game.value] = {"error": str(err)}
                continue

            # Directive 12: Deduplicate candidate boards against batch and database
            unique_boards, collisions = await self.dedup_service.deduplicate_boards(
                db=db,
                candidate_boards=ai_response.boards,
                game_type=game,
                target_date=ref_date,
            )

            if not unique_boards:
                logger.warning(
                    f"All candidate boards for {game.value} were filtered as duplicates ({collisions} collisions). Skipping."
                )
                results_by_game[game.value] = {
                    "boards_count": 0,
                    "duplicates_filtered": collisions,
                }
                continue

            # Persist Boards
            created_for_game: List[GeneratedBoard] = []
            cost_per_board = budget.cost_per_board

            for rec in unique_boards:
                board = GeneratedBoard(
                    budget_id=budget.id,
                    game_type=game.value,
                    target_draw_date=ref_date,
                    numbers=rec.numbers,
                    bonus_or_powerball=rec.bonus_or_powerball,
                    confidence_score=rec.confidence_score,
                    ai_reasoning=rec.reasoning,
                    cost=cost_per_board,
                    status=BoardStatus.PENDING.value,
                )
                db.add(board)
                created_for_game.append(board)

            await db.commit()

            # Deduct quota from monthly budget
            if created_for_game:
                budget = await self.budget_engine.record_board_allocation(
                    db, boards_count=len(created_for_game)
                )
                total_generated += len(created_for_game)
                results_by_game[game.value] = {
                    "boards_count": len(created_for_game),
                    "confidence_scores": [b.confidence_score for b in created_for_game],
                }

        logger.info(
            f"Pre-Draw Pipeline completed: {total_generated} boards generated across {len(results_by_game)} games. "
            f"Remaining budget boards: {budget.remaining_boards}."
        )

        return {
            "status": "COMPLETED",
            "target_date": ref_date.isoformat(),
            "generated_boards_count": total_generated,
            "remaining_budget_boards": budget.remaining_boards,
            "details": results_by_game,
        }

    async def execute_post_draw_pipeline(
        self, db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """Runs the automated Post-Draw Pipeline (Scrape -> Match -> Evaluate -> Feedback)."""
        if db is not None:
            return await self._run_post_draw(db)
        async with self.session_factory() as session:
            return await self._run_post_draw(session)

    async def _run_post_draw(self, db: AsyncSession) -> Dict[str, Any]:
        logger.info("Starting automated Post-Draw Evaluation Pipeline...")

        # 1. Scrape latest official results for all games
        scrape_results = await self.scraper_service.scrape_and_sync_all_games(db)
        logger.info(f"Scraper results: {scrape_results}")

        # 2. Evaluate pending boards against available draws
        total_evaluated = 0
        evaluated_draw_ids = set()

        pending_query = (
            select(GeneratedBoard)
            .where(GeneratedBoard.status == BoardStatus.PENDING.value)
            .order_by(GeneratedBoard.target_draw_date.asc())
        )
        res = await db.execute(pending_query)
        pending_boards = list(res.scalars().all())

        logger.info(f"Found {len(pending_boards)} pending generated boards to evaluate.")

        for board in pending_boards:
            draw_query = (
                select(Draw)
                .where(
                    Draw.game_type == board.game_type,
                    Draw.draw_date == board.target_draw_date,
                )
                .order_by(Draw.draw_number.desc())
                .limit(1)
            )
            draw_res = await db.execute(draw_query)
            draw = draw_res.scalar_one_or_none()

            if not draw:
                continue

            # Directive 14: Evaluate against official SA prize tier matrix
            evaluation = self.prize_service.evaluate_board(
                game_type=GameType(board.game_type),
                board_numbers=board.numbers,
                board_special=board.bonus_or_powerball,
                winning_numbers=draw.numbers,
                winning_bonus=draw.bonus_ball,
                winning_powerball=draw.powerball,
                cost_per_board=board.cost or Decimal(str(settings.COST_PER_BOARD)),
            )

            board.status = BoardStatus.WON.value if evaluation.is_winner else BoardStatus.LOST.value
            board.draw_id = draw.id

            result_entity = BoardResult(
                board_id=board.id,
                draw_id=draw.id,
                matched_numbers=evaluation.matched_numbers,
                matched_count=evaluation.matched_count,
                matched_bonus=evaluation.matched_bonus,
                division=evaluation.division,
                prize_amount=evaluation.prize_amount,
            )
            db.add(result_entity)
            total_evaluated += 1
            evaluated_draw_ids.add(draw.id)

        await db.commit()

        # 3. Broadcast notifications & Trigger Post-Draw AI Feedback Loop for evaluated draws
        feedback_summaries = {}
        if evaluated_draw_ids:
            for draw_id in evaluated_draw_ids:
                draw = await db.get(Draw, draw_id)
                if not draw:
                    continue

                b_res = await db.execute(
                    select(GeneratedBoard).where(GeneratedBoard.draw_id == draw_id)
                )
                boards = list(b_res.scalars().all())

                r_res = await db.execute(
                    select(BoardResult).where(BoardResult.draw_id == draw_id)
                )
                results = list(r_res.scalars().all())

                # Calculate Macro Financial ROI across evaluated draw
                total_winnings = sum((r.prize_amount for r in results), Decimal("0.00"))
                total_cost = sum((b.cost for b in boards), Decimal("0.00"))
                net_profit = total_winnings - total_cost
                roi_pct = float((net_profit / total_cost) * 100) if total_cost > 0 else 0.0

                # Directive alerts: High matches & Draw ROI Summary
                winning_results = [r for r in results if r.prize_amount > Decimal("0.00")]
                if winning_results:
                    win_payload = [
                        {
                            "board_id": r.board_id,
                            "matched_count": r.matched_count,
                            "division": r.division,
                            "prize": r.prize_amount,
                        }
                        for r in winning_results
                    ]
                    await self.notifier.notify_high_matches(
                        game_type=draw.game_type,
                        draw_number=draw.draw_number,
                        winning_boards=win_payload,
                        total_prize=total_winnings,
                    )

                await self.notifier.notify_draw_summary(
                    game_type=draw.game_type,
                    draw_date=draw.draw_date.isoformat(),
                    total_boards=len(boards),
                    total_winnings=total_winnings,
                    roi_percentage=roi_pct,
                )

                if boards:
                    try:
                        fb = await self.ai_service.analyze_draw_performance(draw, boards, results)
                        feedback_summaries[f"draw_{draw_id}"] = {
                            "accuracy": fb.accuracy_rate,
                            "recommendations": fb.calibration_recommendations,
                        }
                    except Exception as fb_err:
                        logger.error(f"Feedback loop error for draw #{draw_id}: {fb_err}")

        logger.info(
            f"Post-Draw Pipeline complete: {total_evaluated} boards evaluated across {len(evaluated_draw_ids)} draws."
        )

        return {
            "status": "COMPLETED",
            "evaluated_boards_count": total_evaluated,
            "evaluated_draws_count": len(evaluated_draw_ids),
            "feedback_summaries": feedback_summaries,
        }

    async def execute_weekly_temporal_analysis(
        self,
        game_types: Optional[List[GameType]] = None,
        analysis_date: Optional[date] = None,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """Executes weekly temporal variance review for all supported games.

        Directive 11: Saves weekly frequency maps, co-occurrence matrices, and actionable bias.
        """
        if db is not None:
            return await self._run_weekly_temporal_analysis(db, game_types, analysis_date)
        async with self.session_factory() as session:
            return await self._run_weekly_temporal_analysis(session, game_types, analysis_date)

    async def _run_weekly_temporal_analysis(
        self,
        db: AsyncSession,
        game_types: Optional[List[GameType]] = None,
        analysis_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        target_games = game_types or [
            GameType.LOTTO,
            GameType.LOTTO_PLUS_1,
            GameType.LOTTO_PLUS_2,
            GameType.POWERBALL,
            GameType.POWERBALL_PLUS,
        ]
        ref_date = analysis_date or date.today()
        logger.info(f"Starting Weekly Temporal Analysis pipeline for {len(target_games)} games on {ref_date}")

        results = {}
        for game in target_games:
            try:
                record = await self.analytics_service.run_weekly_analysis(db, game, ref_date)
                results[game.value] = {
                    "id": record.id,
                    "draws_evaluated": record.sample_draws_count,
                    "sum_average": record.sum_average,
                    "parity_ratio": record.parity_ratio,
                    "actionable_bias": record.actionable_bias_for_generation,
                }
            except Exception as exc:
                logger.error(f"Weekly temporal analysis failed for {game.value}: {exc}")
                results[game.value] = {"error": str(exc)}

        return {
            "status": "COMPLETED",
            "analysis_date": ref_date.isoformat(),
            "games_processed": results,
        }
