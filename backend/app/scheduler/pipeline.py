"""Automated pipeline orchestrating Scraper -> Stats -> AI -> Budget -> Save -> Feedback.

Adheres strictly to:
- Directive 3: Budget Circuit Breaker check before board generation.
- Directive 4: Idempotent scraping (ON CONFLICT DO NOTHING).
- Directive 5: Separation of Concerns (scraper, stats, ai, budget).
- Directive 6: Tenacity retries and graceful fallback.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.budget.engine import BudgetEngine, BudgetExhaustedException
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.board import BoardResult, GeneratedBoard
from app.models.bundle import GameBundle
from app.models.draw import Draw
from app.schemas.enums import (
    BUNDLE_GAMES,
    BoardStatus,
    BundleType,
    GameType,
)
from app.services.ai_service import AIService, AIServiceError
from app.services.analytics_service import TemporalAnalyticsService
from app.services.dedup_service import DedupService
from app.services.feedback_service import FeedbackService
from app.services.notifier import Notifier
from app.services.prize_service import PrizeService
from app.services.scraper_service import ScraperService
from app.services.stats_service import StatsService

# Directive 21: Group into Game Bundles (one board plays all sub-draws)
SCHEDULED_BUNDLES_BY_WEEKDAY = {
    1: [BundleType.POWERBALL_FAMILY],  # Tuesday: PowerBall + PowerBall Plus
    2: [BundleType.LOTTO_FAMILY],      # Wednesday: Lotto + Plus 1 + Plus 2
    4: [BundleType.POWERBALL_FAMILY],  # Friday: PowerBall + PowerBall Plus
    5: [BundleType.LOTTO_FAMILY],      # Saturday: Lotto + Plus 1 + Plus 2
}

SCHEDULED_GAMES_BY_WEEKDAY = SCHEDULED_BUNDLES_BY_WEEKDAY


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
        self.feedback_service = FeedbackService()
        self.notifier = Notifier()

    @staticmethod
    def get_scheduled_games_for_date(ref_date: Optional[date] = None) -> List[BundleType]:
        """Identifies which lottery bundles have draws on the specified date."""
        d = ref_date or date.today()
        weekday = d.weekday()
        return SCHEDULED_BUNDLES_BY_WEEKDAY.get(weekday, [])

    @staticmethod
    def get_scheduled_bundles_for_date(ref_date: Optional[date] = None) -> List[BundleType]:
        return PipelineOrchestrator.get_scheduled_games_for_date(ref_date)

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
        game_types: Optional[List[Any]] = None,
        target_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        ref_date = target_date or date.today()
        raw_items = game_types or self.get_scheduled_bundles_for_date(ref_date)

        # Resolve to distinct BundleTypes
        bundles: List[BundleType] = []
        for it in raw_items:
            s = it.value if hasattr(it, "value") else str(it)
            if s in ("LOTTO_FAMILY", "POWERBALL_FAMILY"):
                b = BundleType(s)
            elif "POWERBALL" in s:
                b = BundleType.POWERBALL_FAMILY
            else:
                b = BundleType.LOTTO_FAMILY
            if b not in bundles:
                bundles.append(b)

        if not bundles:
            logger.info(f"No lottery bundles scheduled for {ref_date} (weekday={ref_date.weekday()}).")
            return {
                "status": "SKIPPED",
                "message": f"No draws scheduled for {ref_date}.",
                "generated_boards_count": 0,
            }

        logger.info(f"Starting Pre-Draw Pipeline for {len(bundles)} bundles on {ref_date}: {[b.value for b in bundles]}")

        total_generated = 0
        results_by_game = {}
        cycle_key = self.budget_engine.current_year_month(ref_date)

        # 1. Directive 3 Circuit Breaker Check
        try:
            allowed, budget = await self.budget_engine.check_circuit_breaker(db, boards_requested=1, year_month=cycle_key)
        except BudgetExhaustedException as exc:
            logger.error(f"Pre-Draw Pipeline HALTED: {exc}")
            await self.notifier.notify_budget_exhaustion(
                year_month=cycle_key,
                remaining_boards=0,
                total_budget=str(settings.DEFAULT_MONTHLY_BUDGET),
            )
            return {
                "status": "HALTED",
                "reason": "Budget Exhausted",
                "remaining_boards": 0,
                "generated_boards_count": 0,
            }

        # 2. Iterate each scheduled bundle
        for bundle in bundles:
            if budget.remaining_boards <= 0:
                logger.warning("Monthly budget exhausted mid-pipeline. Halting subsequent bundles.")
                break

            logger.info(f"Processing pre-draw analysis for bundle {bundle.value}...")

            # Directive 21 & 22: Multi-draw Statistical Pre-Processing across all sub-draws in bundle
            bundle_data = await self.stats_service.get_stats_for_bundle(db, bundle, sample_size=50)
            stats_vars = self.stats_service.format_bundle_prompt_variables(bundle_data)

            # Rolling realized-outcome calibration (aggregate only, never raw draws)
            feedback_summary = await self.feedback_service.get_performance_summary(
                db, bundle.value
            )
            feedback_context = self.feedback_service.format_prompt_context(
                feedback_summary
            )

            # Determine board allocation using confidence engine (Phase 1.5: threshold > 90%)
            allocation = await self.budget_engine.calculate_confidence_allocation(
                db,
                game_type=bundle.value,
                target_date=ref_date,
                performance_summary=feedback_summary,
            )
            boards_to_generate = allocation.total_allocated

            if boards_to_generate <= 0:
                logger.info(f"Allocation for {bundle.value} is 0 boards. Skipping.")
                continue

            # Directive 16: Check environmental correlations across bundle draws (p < 0.05 only)
            env_report = self.stats_service.calculate_environmental_correlations(bundle_data["all_draws"])
            env_anomalies = env_report.llm_prompt_summary if env_report.has_significant_anomalies else None

            # Directive 11: Fetch actionable temporal bias if available
            temporal_bias = await self.analytics_service.get_latest_actionable_bias(db, bundle.value)

            # Generate Boards via Qwen-Max with aggregate bundle intersection optimization
            try:
                ai_response = await self.ai_service.generate_boards(
                    game_type=bundle.value,
                    target_draw_date=ref_date,
                    allocated_boards=boards_to_generate,
                    stats_context=stats_vars,
                    temporal_bias=temporal_bias,
                    environmental_anomalies=env_anomalies,
                    historical_draws=bundle_data["all_draws"],
                    feedback_context=feedback_context,
                )
            except AIServiceError as err:
                logger.error(f"AI generation failed for {bundle.value}: {err}. Skipping bundle.")
                results_by_game[bundle.value] = {"error": str(err)}
                continue

            # Directive 12: Deduplicate candidate boards against batch and database
            unique_boards, collisions = await self.dedup_service.deduplicate_boards(
                db=db,
                candidate_boards=ai_response.boards,
                game_type=bundle.value,
                target_date=ref_date,
            )

            if not unique_boards:
                logger.warning(
                    f"All candidate boards for {bundle.value} were filtered as duplicates ({collisions} collisions). Skipping."
                )
                results_by_game[bundle.value] = {
                    "boards_count": 0,
                    "duplicates_filtered": collisions,
                }
                continue

            # Resolve bundle entity from DB
            b_query = select(GameBundle).where(GameBundle.bundle_name == bundle.value)
            b_res = await db.execute(b_query)
            bundle_entity = b_res.scalar_one_or_none()
            cost_per_board = bundle_entity.total_cost_per_board if bundle_entity else budget.cost_per_board

            # Persist Boards
            created_for_bundle: List[GeneratedBoard] = []
            mc_by_numbers = {
                tuple(m["numbers"]): m for m in (ai_response.monte_carlo or [])
            }
            for rec in unique_boards:
                ev_report = self.stats_service.calculate_ev_score(rec.numbers)
                mc_entry = mc_by_numbers.get(tuple(rec.numbers))
                board = GeneratedBoard(
                    bundle_id=bundle_entity.id if bundle_entity else None,
                    budget_id=budget.id,
                    bundle_name=bundle.value,
                    game_type=bundle.value,
                    target_draw_date=ref_date,
                    numbers=rec.numbers,
                    bonus_or_powerball=rec.bonus_or_powerball,
                    confidence_score=rec.confidence_score,
                    ai_reasoning=rec.reasoning,
                    cost=cost_per_board,
                    status=BoardStatus.PENDING.value,
                    simulated_hit_rate=mc_entry["simulated_hit_rate"] if mc_entry else None,
                    ev_score=ev_report.ev_score,
                )
                db.add(board)
                created_for_bundle.append(board)

            await db.commit()

            # Deduct quota from monthly budget
            if created_for_bundle:
                budget = await self.budget_engine.record_board_allocation(
                    db, boards_count=len(created_for_bundle), year_month=cycle_key
                )
                total_generated += len(created_for_bundle)
                results_by_game[bundle.value] = {
                    "boards_count": len(created_for_bundle),
                    "confidence_scores": [b.confidence_score for b in created_for_bundle],
                }

        logger.info(
            f"Pre-Draw Pipeline completed: {total_generated} boards generated across {len(results_by_game)} bundles. "
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
        # Group finalized reviews by (bundle, target_date) so each bundle
        # night yields ONE aggregated feedback record (Directive 24), not one
        # per sub-draw. Key -> {"draw_ids": set, "board_ids": set}.
        evaluated_targets: Dict[Any, Dict[str, set]] = {}

        pending_query = (
            select(GeneratedBoard)
            .where(
                GeneratedBoard.status.in_(
                    [BoardStatus.PENDING.value, BoardStatus.PLAYED.value]
                )
            )
            .order_by(GeneratedBoard.target_draw_date.asc())
        )
        res = await db.execute(pending_query)
        pending_boards = list(res.scalars().all())

        logger.info(f"Found {len(pending_boards)} pending generated boards to evaluate.")

        for board in pending_boards:
            b_name = board.bundle_name or "LOTTO_FAMILY"
            try:
                b_type = BundleType(b_name)
            except ValueError:
                b_type = BundleType.LOTTO_FAMILY
            member_games = [g.value for g in BUNDLE_GAMES.get(b_type, [])]

            # Fetch official draws for member sub-games matching the exact target draw date
            draws_query = (
                select(Draw)
                .where(
                    Draw.game_type.in_(member_games),
                    Draw.draw_date == board.target_draw_date,
                )
                .order_by(Draw.draw_date.asc(), Draw.draw_number.asc())
            )
            draws_res = await db.execute(draws_query)
            matching_draws = list(draws_res.scalars().all())

            if not matching_draws:
                continue

            # Only finalize a bundle board once every scheduled sub-draw is present.
            # Otherwise a partial scrape would permanently understate winnings/ROI.
            expected_games = set(member_games)
            available_games = {d.game_type for d in matching_draws}
            if not expected_games.issubset(available_games):
                missing = sorted(expected_games - available_games)
                logger.info(
                    f"Deferring board #{board.id} ({b_name}) evaluation for "
                    f"{board.target_draw_date}: missing sub-draws {missing}."
                )
                continue

            # Directive 24: Multi-Draw ROI Evaluation - evaluate board against all sub-draws
            bundle_eval = self.prize_service.evaluate_board_against_bundle_draws(
                board_numbers=board.numbers,
                board_special=board.bonus_or_powerball,
                draws=matching_draws,
                bundle_name=b_name,
                cost_per_board=board.cost or Decimal("10.00"),
                board_id=board.id,
            )

            board.status = BoardStatus.WON.value if bundle_eval.is_winner else BoardStatus.LOST.value
            board.draw_id = matching_draws[0].id

            for draw in matching_draws:
                sub_eval = bundle_eval.sub_evaluations.get(draw.game_type)
                if not sub_eval:
                    continue
                existing_res = await db.execute(
                    select(BoardResult).where(
                        BoardResult.board_id == board.id,
                        BoardResult.draw_id == draw.id,
                    )
                )
                result_entity = existing_res.scalar_one_or_none()
                if result_entity is None:
                    result_entity = BoardResult(
                        board_id=board.id,
                        draw_id=draw.id,
                        game_type=draw.game_type,
                    )
                    db.add(result_entity)
                result_entity.matched_numbers = sub_eval.matched_numbers
                result_entity.matched_count = sub_eval.matched_count
                result_entity.matched_bonus = sub_eval.matched_bonus
                result_entity.division = sub_eval.division
                result_entity.prize_amount = sub_eval.prize_amount
                total_evaluated += 1

            bucket = evaluated_targets.setdefault(
                (b_type.value, board.target_draw_date),
                {"draw_ids": set(), "board_ids": set()},
            )
            bucket["board_ids"].add(board.id)
            bucket["draw_ids"].update(d.id for d in matching_draws)

        await db.commit()

        # 3. One bundle-level notification + one aggregated feedback record
        #    per (bundle, draw_date). Directive 24: sum prizes across sub-draws
        #    against a single board cost so notifications and ROI stay consistent.
        feedback_summaries = {}
        if evaluated_targets:
            for (bundle_key, target_date), info in evaluated_targets.items():
                draw_ids = info["draw_ids"]
                board_ids = info["board_ids"]
                if not draw_ids or not board_ids:
                    continue

                group_results_res = await db.execute(
                    select(BoardResult).where(
                        BoardResult.draw_id.in_(draw_ids),
                        BoardResult.board_id.in_(board_ids),
                    )
                )
                group_results = list(group_results_res.scalars().all())

                group_boards_res = await db.execute(
                    select(GeneratedBoard).where(GeneratedBoard.id.in_(board_ids))
                )
                group_boards = list(group_boards_res.scalars().all())

                group_draws = []
                for did in draw_ids:
                    d = await db.get(Draw, did)
                    if d:
                        group_draws.append(d)
                if not group_draws or not group_boards:
                    continue

                primary_game = BUNDLE_GAMES.get(BundleType(bundle_key), [])
                rep_draw = None
                if primary_game:
                    rep_draw = next(
                        (d for d in group_draws if d.game_type == primary_game[0].value),
                        None,
                    )
                if rep_draw is None:
                    rep_draw = min(group_draws, key=lambda d: d.draw_number)

                total_winnings = sum(
                    (r.prize_amount for r in group_results), Decimal("0.00")
                )
                total_cost = sum(
                    ((b.cost or Decimal("10.00")) for b in group_boards),
                    Decimal("0.00"),
                )
                net_profit = total_winnings - total_cost
                roi_pct = (
                    float((net_profit / total_cost) * 100) if total_cost > 0 else 0.0
                )

                # Bundle-level board breakdown: one entry per board, sub-draw detail inside
                by_board: Dict[int, List[BoardResult]] = {}
                for r in group_results:
                    by_board.setdefault(r.board_id, []).append(r)
                board_evaluations: List[Dict[str, Any]] = []
                for b in sorted(group_boards, key=lambda x: x.id):
                    rs = by_board.get(b.id, [])
                    board_evaluations.append(
                        {
                            "board_id": b.id,
                            "numbers": b.numbers,
                            "bonus_or_pb": b.bonus_or_powerball,
                            "board_total_prize": sum(
                                (r.prize_amount for r in rs), Decimal("0.00")
                            ),
                            "sub_results": [
                                {
                                    "game_type": r.game_type,
                                    "matched_count": r.matched_count,
                                    "matched_numbers": r.matched_numbers,
                                    "division": r.division,
                                    "prize": r.prize_amount,
                                }
                                for r in rs
                            ],
                        }
                    )

                sub_draws = [
                    {
                        "game_type": d.game_type,
                        "draw_number": d.draw_number,
                        "numbers": d.numbers,
                        "bonus_or_pb": d.powerball
                        if "POWERBALL" in d.game_type.upper()
                        else d.bonus_ball,
                    }
                    for d in sorted(group_draws, key=lambda x: x.draw_number)
                ]

                # Notification (failure isolated from feedback persistence)
                try:
                    await self.notifier.notify_bundle_completion(
                        bundle_name=bundle_key,
                        target_date=target_date.isoformat(),
                        sub_draws=sub_draws,
                        board_evaluations=board_evaluations,
                        total_winnings=total_winnings,
                        total_cost=total_cost,
                        roi_percentage=roi_pct,
                    )
                    winning_boards = [
                        be
                        for be in board_evaluations
                        if be["board_total_prize"] > Decimal("0.00")
                    ]
                    if winning_boards:
                        win_payload = []
                        for be in winning_boards:
                            best = max(
                                be["sub_results"],
                                key=lambda sr: sr["matched_count"],
                                default={"matched_count": 0, "division": None},
                            )
                            win_payload.append(
                                {
                                    "board_id": be["board_id"],
                                    "matched_count": best["matched_count"],
                                    "division": best["division"],
                                    "prize": be["board_total_prize"],
                                }
                            )
                        await self.notifier.notify_high_matches(
                            game_type=bundle_key,
                            draw_number=rep_draw.draw_number,
                            winning_boards=win_payload,
                            total_prize=total_winnings,
                        )
                except Exception as notify_err:
                    logger.error(
                        f"Bundle notification failed for {bundle_key} {target_date}: "
                        f"{notify_err}"
                    )

                # Feedback (aggregate + persist)
                try:
                    fb = await self.ai_service.analyze_draw_performance(
                        rep_draw, group_boards, group_results
                    )
                    persisted = False
                    try:
                        await self.feedback_service.record_feedback(
                            db,
                            draw=rep_draw,
                            bundle_name=bundle_key,
                            boards=group_boards,
                            results=group_results,
                            feedback=fb,
                            source="qwen",
                        )
                        persisted = True
                    except Exception as persist_err:
                        logger.error(
                            f"Failed to persist feedback for {bundle_key} {target_date}: "
                            f"{persist_err}"
                        )
                    feedback_summaries[f"{bundle_key}_{target_date.isoformat()}"] = {
                        "accuracy": fb.accuracy_rate,
                        "recommendations": fb.calibration_recommendations,
                        "persisted": persisted,
                        "boards_evaluated": len(group_boards),
                    }
                except Exception as fb_err:
                    logger.error(
                        f"Feedback loop error for {bundle_key} {target_date}: {fb_err}"
                    )
        else:
            # Fallback: no user boards pending; broadcast newly scraped results per draw
            today = date.today()
            recent_draws_res = await db.execute(
                select(Draw)
                .where(Draw.draw_date >= today - timedelta(days=2))
                .order_by(Draw.draw_date.desc(), Draw.id.desc())
            )
            recent_draws = list(recent_draws_res.scalars().all())
            notified_games = set()
            for draw in recent_draws:
                if draw.game_type not in notified_games:
                    notified_games.add(draw.game_type)
                    special_ball = draw.powerball if "POWERBALL" in draw.game_type.upper() else draw.bonus_ball
                    await self.notifier.notify_draw_completion(
                        game_type=draw.game_type,
                        draw_number=draw.draw_number,
                        draw_date=draw.draw_date.isoformat(),
                        winning_numbers=draw.numbers,
                        bonus_or_pb=special_ball,
                        board_evaluations=[],
                        total_winnings=Decimal("0.00"),
                        total_cost=Decimal("0.00"),
                        roi_percentage=0.0,
                    )

        evaluated_boards = {
            bid for info in evaluated_targets.values() for bid in info["board_ids"]
        }
        evaluated_draws = {
            did for info in evaluated_targets.values() for did in info["draw_ids"]
        }

        logger.info(
            f"Post-Draw Pipeline complete: {len(evaluated_boards)} boards across "
            f"{total_evaluated} sub-results / {len(evaluated_draws)} draws."
        )

        return {
            "status": "COMPLETED",
            "evaluated_sub_results": total_evaluated,
            "evaluated_boards_count": len(evaluated_boards),
            "evaluated_draws_count": len(evaluated_draws),
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
