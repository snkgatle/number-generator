"""Generator Router - endpoints for AI-driven board generation, retrieval, and post-draw feedback."""
from datetime import date
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.board import BoardResult, GeneratedBoard
from app.models.draw import Draw
from app.schemas.board import (
    BoardWithResultResponse,
    GeneratedBoardResponse,
    GenerationRequest,
    PostDrawFeedbackResponse,
    PreDrawPipelineRequest,
)
from app.schemas.enums import GameType
from app.services.ai_service import AIService, AIServiceError
from app.services.budget_service import BudgetExhaustedException, BudgetService
from app.services.stats_service import StatsService

router = APIRouter(prefix="/generator", tags=["Generator"])
ai_service = AIService()
stats_service = StatsService()
budget_service = BudgetService()


@router.get("/boards", response_model=List[GeneratedBoardResponse])
async def list_generated_boards(
    game_type: Optional[GameType] = Query(None, description="Filter by lottery game type"),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve generated lottery boards sorted by creation timestamp descending."""
    query = select(GeneratedBoard).order_by(GeneratedBoard.created_at.desc()).limit(limit)
    if game_type:
        query = query.where(GeneratedBoard.game_type == game_type.value)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/boards/{board_id}", response_model=BoardWithResultResponse)
async def get_board_by_id(
    board_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a single generated board including its post-draw match results if evaluated."""
    query = select(GeneratedBoard).where(GeneratedBoard.id == board_id)
    result = await db.execute(query)
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generated board #{board_id} not found.",
        )
    return board


@router.post("/generate", response_model=List[GeneratedBoardResponse], status_code=status.HTTP_201_CREATED)
async def generate_boards(
    payload: GenerationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Trigger AI generation pipeline subject to Directive 3 Budget Circuit Breaker."""
    requested_boards = payload.allocated_boards or 1

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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Budget Exhausted. Board generation halted by Circuit Breaker.",
        )

    # Phase 3: Statistical Pre-Processing (Executed locally in Python before calling LLM)
    stats = await stats_service.get_stats_for_game(db, payload.game_type, sample_size=50)
    prompt_vars = stats_service.format_prompt_variables(stats)

    target_date = payload.target_draw_date or date.today()

    # Phase 4: Qwen-Max Generation with Strict JSON Enforcement
    try:
        ai_response = await ai_service.generate_boards(
            game_type=payload.game_type,
            target_draw_date=target_date,
            allocated_boards=requested_boards,
            stats_context=prompt_vars,
        )
    except AIServiceError as err:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI generation service error: {err}",
        )

    # Persist generated boards and deduct quota
    created_boards: List[GeneratedBoard] = []
    board_cost = Decimal(str(settings.COST_PER_BOARD))

    for rec in ai_response.boards:
        board_entity = GeneratedBoard(
            budget_id=budget.id,
            game_type=payload.game_type.value,
            target_draw_date=target_date,
            numbers=rec.numbers,
            bonus_or_powerball=rec.bonus_or_powerball,
            confidence_score=rec.confidence_score,
            ai_reasoning=rec.reasoning,
            cost=board_cost,
            status="PENDING",
        )
        db.add(board_entity)
        created_boards.append(board_entity)

    await db.commit()

    # Deduct quota from monthly budget
    await budget_service.record_board_usage(db, boards_used=len(created_boards))

    # Refresh entities for response serialization
    for b in created_boards:
        await db.refresh(b)

    return created_boards


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

    # 2. Fetch associated boards and results
    boards_res = await db.execute(
        select(GeneratedBoard).where(GeneratedBoard.draw_id == draw_id)
    )
    boards = list(boards_res.scalars().all())

    results_res = await db.execute(
        select(BoardResult).where(BoardResult.draw_id == draw_id)
    )
    results = list(results_res.scalars().all())

    try:
        feedback = await ai_service.analyze_draw_performance(draw, boards, results)
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
