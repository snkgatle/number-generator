"""Unit tests for DedupService (Directive 12).

Tests hash-based collision detection across generated boards.
"""
from datetime import date
from decimal import Decimal
import pytest
from app.models.board import GeneratedBoard
from app.schemas.board import AIBoardRecommendation
from app.schemas.enums import GameType
from app.services.dedup_service import DedupService


@pytest.fixture
def dedup_service():
    return DedupService()


def test_fingerprint_order_invariance(dedup_service):
    """Numbers order should not change the canonical SHA-256 hash."""
    h1 = dedup_service.compute_board_fingerprint(
        numbers=[5, 12, 23, 34, 45, 50],
        bonus_or_powerball=None,
        game_type="LOTTO",
        target_date=date(2026, 10, 21),
    )
    h2 = dedup_service.compute_board_fingerprint(
        numbers=[50, 23, 5, 45, 12, 34],
        bonus_or_powerball=None,
        game_type="LOTTO",
        target_date=date(2026, 10, 21),
    )
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex string


def test_fingerprint_sensitivity(dedup_service):
    """Different powerball, game, date, or numbers must produce distinct hashes."""
    base = dedup_service.compute_board_fingerprint(
        numbers=[5, 12, 23, 34, 45],
        bonus_or_powerball=10,
        game_type="POWERBALL",
        target_date=date(2026, 10, 20),
    )
    diff_pb = dedup_service.compute_board_fingerprint(
        numbers=[5, 12, 23, 34, 45],
        bonus_or_powerball=11,
        game_type="POWERBALL",
        target_date=date(2026, 10, 20),
    )
    diff_date = dedup_service.compute_board_fingerprint(
        numbers=[5, 12, 23, 34, 45],
        bonus_or_powerball=10,
        game_type="POWERBALL",
        target_date=date(2026, 10, 23),
    )
    assert base != diff_pb
    assert base != diff_date


@pytest.mark.asyncio
async def test_deduplicate_batch_internal_duplicates(dedup_service, db_session):
    """Filters duplicate boards within the same candidate recommendation batch."""
    candidates = [
        AIBoardRecommendation(
            numbers=[1, 2, 3, 4, 5, 6],
            bonus_or_powerball=None,
            confidence_score=80.0,
            reasoning="Statistical reasoning for candidate board 1",
        ),
        AIBoardRecommendation(
            numbers=[6, 5, 4, 3, 2, 1],  # Duplicate of board 1 in reverse order
            bonus_or_powerball=None,
            confidence_score=75.0,
            reasoning="Duplicate candidate board with reversed order",
        ),
        AIBoardRecommendation(
            numbers=[10, 20, 30, 40, 41, 42],
            bonus_or_powerball=None,
            confidence_score=85.0,
            reasoning="Unique statistical board recommendation 3",
        ),
    ]

    unique, collisions = await dedup_service.deduplicate_boards(
        db=db_session,
        candidate_boards=candidates,
        game_type=GameType.LOTTO,
        target_date=date(2026, 10, 21),
    )

    assert len(unique) == 2
    assert collisions == 1
    assert unique[0].numbers == [1, 2, 3, 4, 5, 6]
    assert unique[1].numbers == [10, 20, 30, 40, 41, 42]


@pytest.mark.asyncio
async def test_deduplicate_against_db_existing_boards(dedup_service, db_session):
    """Filters candidate boards that collide with previously persisted boards for target date."""
    target_date = date(2026, 10, 21)

    # Seed an existing board in DB
    existing = GeneratedBoard(
        game_type="LOTTO",
        target_draw_date=target_date,
        numbers=[7, 14, 21, 28, 35, 42],
        bonus_or_powerball=None,
        confidence_score=90.0,
        ai_reasoning="Historical Board",
        cost=Decimal("5.00"),
        status="PENDING",
    )
    db_session.add(existing)
    await db_session.commit()

    candidates = [
        AIBoardRecommendation(
            numbers=[7, 14, 21, 28, 35, 42],  # Collides with DB
            bonus_or_powerball=None,
            confidence_score=80.0,
            reasoning="Colliding with previously saved board",
        ),
        AIBoardRecommendation(
            numbers=[2, 4, 6, 8, 10, 12],  # Brand new
            bonus_or_powerball=None,
            confidence_score=88.0,
            reasoning="Unique brand new board recommendation",
        ),
    ]

    unique, collisions = await dedup_service.deduplicate_boards(
        db=db_session,
        candidate_boards=candidates,
        game_type=GameType.LOTTO,
        target_date=target_date,
    )

    assert len(unique) == 1
    assert collisions == 1
    assert unique[0].numbers == [2, 4, 6, 8, 10, 12]
