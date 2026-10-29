"""Generator Router - endpoints for AI-driven board generation, retrieval, and post-draw feedback."""
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.models.board import BoardResult, GeneratedBoard
from app.models.bundle import GameBundle
from app.models.draw import Draw
from app.schemas.board import (
    BoardWithResultResponse,
    GeneratedBoardResponse,
    GenerationRequest,
    PostDrawFeedbackResponse,
    PreDrawPipelineRequest,
)
from app.schemas.enums import BundleType, GameType, GAME_TO_BUNDLE, BUNDLE_GAMES, get_next_draw_date
from app.schemas.feedback import FeedbackPerformanceSummary, GenerationFeedbackResponse
from app.services.ai_service import AIService, AIServiceError
from app.services.analytics_service import TemporalAnalyticsService
from app.services.budget_service import BudgetExhaustedException, BudgetService
from app.services.dedup_service import DedupService
from app.services.feedback_service import FeedbackService
from app.services.notifier import Notifier
from app.services.stats_service import StatsService

router = APIRouter(prefix="/generator", tags=["Generator"])
ai_service = AIService()
stats_service = StatsService()
budget_service = BudgetService()
analytics_service = TemporalAnalyticsService(ai_service)
dedup_service = DedupService()
feedback_service = FeedbackService()
notifier = Notifier()


@router.get("/boards", response_model=List[BoardWithResultResponse])
async def list_generated_boards(
    game_type: Optional[GameType] = Query(None, description="Filter by lottery game type"),
    bundle_name: Optional[BundleType] = Query(None, description="Filter by game bundle"),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve generated lottery boards sorted by creation timestamp descending."""
    query = (
        select(GeneratedBoard)
        .options(selectinload(GeneratedBoard.results))
        .order_by(GeneratedBoard.created_at.desc())
        .limit(limit)
    )
    if bundle_name:
        query = query.where(GeneratedBoard.bundle_name == bundle_name.value)
    elif game_type:
        b_type = GAME_TO_BUNDLE.get(game_type)
        if b_type:
            query = query.where(GeneratedBoard.bundle_name == b_type.value)
        else:
            query = query.where(GeneratedBoard.bundle_name == game_type.value)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/boards/{board_id}", response_model=BoardWithResultResponse)
async def get_board_by_id(
    board_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a single generated board including its post-draw match results if evaluated."""
    query = (
        select(GeneratedBoard)
        .options(selectinload(GeneratedBoard.results))
        .where(GeneratedBoard.id == board_id)
    )
    result = await db.execute(query)
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generated board #{board_id} not found.",
        )
    return board


@router.patch("/boards/{board_id}/played", response_model=BoardWithResultResponse)
async def toggle_board_played(
    board_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Directive 10: Toggle the manual-played flag on a pending board.

    Marks the board as PLAYED once the user has entered it on the official
    lottery platform, or reverts it to PENDING. Evaluated boards cannot change.
    """
    query = (
        select(GeneratedBoard)
        .options(selectinload(GeneratedBoard.results))
        .where(GeneratedBoard.id == board_id)
    )
    result = await db.execute(query)
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generated board #{board_id} not found.",
        )

    if board.status not in ("PENDING", "PLAYED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Board #{board_id} is already evaluated ({board.status}); played flag cannot change.",
        )

    if board.status == "PLAYED":
        board.status = "PENDING"
        board.played_at = None
    else:
        board.status = "PLAYED"
        board.played_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(board)
    return board


@router.post("/generate", response_model=List[GeneratedBoardResponse], status_code=status.HTTP_201_CREATED)
async def generate_boards(
    payload: GenerationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Trigger AI generation pipeline subject to Directive 3 Budget Circuit Breaker."""
    requested_boards = payload.allocated_boards or 1
    bundle_type = payload.resolved_bundle()
    target_date = payload.target_draw_date or get_next_draw_date(bundle_type)
    cycle_key = budget_service.current_year_month(target_date)

    # Query GameBundle entity to link bundle_id and cost
    bundle_res = await db.execute(
        select(GameBundle).where(GameBundle.bundle_name == bundle_type.value)
    )
    bundle_entity = bundle_res.scalar_one_or_none()
    bundle_id = bundle_entity.id if bundle_entity else None
    board_cost = bundle_entity.total_cost_per_board if bundle_entity else Decimal(str(settings.COST_PER_BOARD))

    # Directive 3: Budget Circuit Breaker check
    try:
        allowed, budget = await budget_service.verify_circuit_breaker(
            db, boards_requested=requested_boards
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Requested {requested_boards} boards exceeds remaining monthly quota "
                    f"of {budget.remaining_boards} boards."
                ),
            )
    except BudgetExhaustedException:
        await notifier.notify_budget_exhaustion(
            year_month=cycle_key,
            remaining_boards=0,
            total_budget=str(settings.DEFAULT_MONTHLY_BUDGET),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Budget Exhausted. Board generation halted by Circuit Breaker.",
        )

    # Directive 21 & 22: Bundle Statistical Pre-Processing across all sub-draws
    bundle_stats = await stats_service.get_stats_for_bundle(db, bundle_type, sample_size=50)
    recent_draws = await stats_service.get_recent_draws(db, bundle_type, limit=50)
    prompt_vars = stats_service.format_bundle_prompt_variables(bundle_stats, recent_draws=recent_draws)

    # Directive 16: Guardrailed environmental metadata test (p < 0.05 only)
    env_report = stats_service.calculate_environmental_correlations(recent_draws)
    env_anomalies = env_report.llm_prompt_summary if env_report.has_significant_anomalies else None

    # Directive 11: Fetch actionable temporal bias
    temporal_bias = await analytics_service.get_latest_actionable_bias(db, bundle_type)

    # Realized-outcome calibration from complete prior evaluations (aggregate only)
    feedback_summary = await feedback_service.get_performance_summary(
        db, bundle_type.value
    )
    feedback_context = feedback_service.format_prompt_context(feedback_summary)

    # Phase 4: Qwen-Max Generation with Strict JSON Enforcement & Monte Carlo Stress Testing (Directive 15)
    try:
        ai_response = await ai_service.generate_boards(
            game_type=bundle_type,
            target_draw_date=target_date,
            allocated_boards=requested_boards,
            stats_context=prompt_vars,
            temporal_bias=temporal_bias,
            environmental_anomalies=env_anomalies,
            historical_draws=recent_draws,
            feedback_context=feedback_context,
        )
    except AIServiceError as err:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI generation service error: {err}",
        )

    # Directive 12: Deduplicate generated candidate boards
    unique_boards, collisions = await dedup_service.deduplicate_boards(
        db=db,
        candidate_boards=ai_response.boards,
        game_type=bundle_type,
        target_date=target_date,
    )

    if not unique_boards:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"All {len(ai_response.boards)} candidate boards already exist for {target_date}.",
        )

    # Persist generated boards and deduct quota
    created_boards: List[GeneratedBoard] = []

    # Directive 15: map Monte Carlo results back to boards surviving dedup
    mc_by_numbers = {
        tuple(m["numbers"]): m for m in (ai_response.monte_carlo or [])
    }

    for rec in unique_boards:
        # Directive 20: compute EV score locally (fast, deterministic)
        ev_report = stats_service.calculate_ev_score(rec.numbers)
        mc_entry = mc_by_numbers.get(tuple(rec.numbers))
        board_entity = GeneratedBoard(
            bundle_id=bundle_id,
            budget_id=budget.id,
            bundle_name=bundle_type.value,
            game_type=bundle_type.value,
            target_draw_date=target_date,
            numbers=rec.numbers,
            bonus_or_powerball=rec.bonus_or_powerball,
            confidence_score=rec.confidence_score,
            ai_reasoning=rec.reasoning,
            cost=board_cost,
            status="PENDING",
            simulated_hit_rate=mc_entry["simulated_hit_rate"] if mc_entry else None,
            ev_score=ev_report.ev_score,
        )
        db.add(board_entity)
        created_boards.append(board_entity)

    await db.commit()

    # Deduct quota from monthly budget
    await budget_service.record_board_usage(db, boards_used=len(created_boards), year_month=cycle_key)

    # Refresh entities for response serialization
    for b in created_boards:
        await db.refresh(b)

    return created_boards


@router.get("/feedback", response_model=List[GenerationFeedbackResponse])
async def list_performance_feedback(
    bundle_name: Optional[BundleType] = Query(None, description="Filter by game bundle"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve persisted post-draw performance feedback, newest first."""
    return await feedback_service.get_recent_feedback(
        db,
        bundle_name=bundle_name.value if bundle_name else None,
        limit=limit,
    )


@router.get("/feedback/performance", response_model=FeedbackPerformanceSummary)
async def get_performance_summary(
    bundle_name: BundleType = Query(..., description="Bundle to summarize"),
    db: AsyncSession = Depends(get_db),
):
    """Return the rolling realized-outcome summary used for future calibration."""
    return await feedback_service.get_performance_summary(db, bundle_name.value)


@router.post("/feedback/{draw_id}", response_model=PostDrawFeedbackResponse)
async def post_draw_feedback(
    draw_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Executes the post-draw feedback loop analyzing deviations between predictions and official results."""
    # 1. Fetch Draw
    draw_res = await db.execute(select(Draw).where(Draw.id == draw_id))
    draw = draw_res.scalar_one_or_none()
    if not draw:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Draw #{draw_id} not found.",
        )

    # 2. Resolve the parent bundle so this review aggregates every sub-draw on
    #    the same night (Directive 24), matching the batch pipeline's keying.
    try:
        bundle_type = GAME_TO_BUNDLE.get(GameType(draw.game_type))
    except ValueError:
        bundle_type = None
    if bundle_type is None:
        bundle_type = BundleType.LOTTO_FAMILY

    member_games = [g.value for g in BUNDLE_GAMES.get(bundle_type, [])]
    siblings_res = await db.execute(
        select(Draw).where(
            Draw.game_type.in_(member_games),
            Draw.draw_date == draw.draw_date,
        )
    )
    sibling_draws = list(siblings_res.scalars().all()) or [draw]
    sibling_ids = {d.id for d in sibling_draws}

    # Representative draw = the bundle's primary sub-draw (stable feedback key).
    primary_game = BUNDLE_GAMES[bundle_type][0].value if member_games else draw.game_type
    representative = next(
        (d for d in sibling_draws if d.game_type == primary_game),
        min(sibling_draws, key=lambda d: d.draw_number),
    )

    results_res = await db.execute(
        select(BoardResult).where(BoardResult.draw_id.in_(sibling_ids))
    )
    results = list(results_res.scalars().all())

    board_ids = {r.board_id for r in results}
    boards: List[GeneratedBoard] = []
    if board_ids:
        boards_res = await db.execute(
            select(GeneratedBoard).where(GeneratedBoard.id.in_(board_ids))
        )
        boards = list(boards_res.scalars().all())

    try:
        feedback = await ai_service.analyze_draw_performance(representative, boards, results)

        if boards:
            try:
                await feedback_service.record_feedback(
                    db,
                    draw=representative,
                    bundle_name=bundle_type.value,
                    boards=boards,
                    results=results,
                    feedback=feedback,
                    source="manual",
                )
            except Exception as persist_err:
                logger.error(
                    f"Failed to persist manual feedback for draw #{draw_id}: {persist_err}"
                )

        return feedback
    except AIServiceError as err:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI feedback analysis failed: {err}",
        )


@router.post("/pipeline/pre-draw")
async def trigger_pre_draw_pipeline(
    payload: Optional[PreDrawPipelineRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """Manually triggers the automated Pre-Draw Pipeline (Stats -> AI -> Budget -> Save)."""
    from app.scheduler import pipeline_orchestrator
    games = payload.game_types if payload else None
    t_date = payload.target_date if payload else None
    result = await pipeline_orchestrator.execute_pre_draw_pipeline(
        game_types=games, target_date=t_date, db=db
    )
    if result.get("status") == "HALTED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Budget Exhausted. Board generation halted by Circuit Breaker.",
        )
    return result


@router.post("/pipeline/post-draw")
async def trigger_post_draw_pipeline(
    db: AsyncSession = Depends(get_db),
):
    """Manually triggers the automated Post-Draw Pipeline (Scrape -> Match -> Evaluate -> Feedback)."""
    from app.scheduler import pipeline_orchestrator
    return await pipeline_orchestrator.execute_post_draw_pipeline(db=db)


@router.post("/pipeline/weekly-temporal")
async def trigger_weekly_temporal_pipeline(
    db: AsyncSession = Depends(get_db),
):
    """Manually triggers the weekly temporal variance review for all games."""
    from app.scheduler import pipeline_orchestrator
    return await pipeline_orchestrator.execute_weekly_temporal_analysis(db=db)


@router.post("/test-telegram")
async def test_telegram_alert():
    """Test endpoint to trigger a verification message to Telegram from the backend."""
    success = await notifier.send_telegram(
        "🎰 *LottoMind Telegram Alert System*\n\n"
        "✅ Verified: Cloud Run can successfully communicate with your Telegram Bot!\n"
        "• Channel: Private Alerts\n"
        "• Triggers: High Matches, Payout ROI, Budget Circuit Breaker"
    )
    return {
        "success": success,
        "token_configured": bool(notifier.telegram_token),
        "chat_id_configured": bool(notifier.telegram_chat_id),
    }
