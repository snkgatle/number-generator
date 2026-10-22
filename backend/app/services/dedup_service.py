"""Board Deduplication Service implementing hash-based collision checks.

Directive 12: Implement a hash-based collision check across all generated
boards for a single draw date to prevent duplicate plays.
"""
from datetime import date
import hashlib
from typing import List, Optional, Set, Tuple, Union
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board import GeneratedBoard
from app.schemas.board import AIBoardRecommendation
from app.schemas.enums import BundleType, GameType


class DedupService:
    """Provides cryptographic hash-based board fingerprinting and collision detection."""

    @staticmethod
    def compute_board_fingerprint(
        numbers: List[int],
        bonus_or_powerball: Optional[int] = None,
        game_type: Optional[str] = None,
        target_date: Optional[date] = None,
    ) -> str:
        """Computes a SHA-256 fingerprint for a board configuration.

        Canonical format ensures sorted numbers produce identical hash regardless of input order.
        """
        sorted_nums = sorted(numbers)
        pb_part = str(bonus_or_powerball) if bonus_or_powerball is not None else "null"
        game_part = str(game_type) if game_type else "any"
        date_part = target_date.isoformat() if target_date else "any"

        canonical_repr = f"game={game_part}|date={date_part}|nums={sorted_nums}|pb={pb_part}"
        return hashlib.sha256(canonical_repr.encode("utf-8")).hexdigest()

    async def get_existing_board_hashes(
        self, db: AsyncSession, game_type: Union[GameType, BundleType, str], target_date: date
    ) -> Set[str]:
        """Queries the database for existing boards on target date and returns their fingerprints."""
        raw_val = game_type.value if hasattr(game_type, "value") else str(game_type)
        query = select(GeneratedBoard).where(
            (GeneratedBoard.bundle_name == raw_val),
            GeneratedBoard.target_draw_date == target_date,
        )
        result = await db.execute(query)
        existing_boards = list(result.scalars().all())

        hashes = {
            self.compute_board_fingerprint(
                numbers=b.numbers,
                bonus_or_powerball=b.bonus_or_powerball,
                game_type=b.bundle_name,
                target_date=b.target_draw_date,
            )
            for b in existing_boards
        }
        logger.debug(
            f"Found {len(hashes)} existing board fingerprints for {raw_val} on {target_date}."
        )
        return hashes

    async def deduplicate_boards(
        self,
        db: AsyncSession,
        candidate_boards: List[AIBoardRecommendation],
        game_type: Union[GameType, BundleType, str],
        target_date: date,
    ) -> Tuple[List[AIBoardRecommendation], int]:
        """Filters duplicate boards across the candidate list and existing database entries.

        Directive 12: Prevents duplicate plays on a single draw date.
        Returns:
            Tuple of (unique_boards, duplicates_filtered_count)
        """
        raw_val = game_type.value if hasattr(game_type, "value") else str(game_type)
        existing_hashes = await self.get_existing_board_hashes(db, raw_val, target_date)
        seen_in_batch: Set[str] = set()

        unique_boards: List[AIBoardRecommendation] = []
        collisions_count = 0

        for board in candidate_boards:
            h = self.compute_board_fingerprint(
                numbers=board.numbers,
                bonus_or_powerball=board.bonus_or_powerball,
                game_type=raw_val,
                target_date=target_date,
            )

            if h in existing_hashes:
                logger.warning(
                    f"Collision detected with historical board for {raw_val} on {target_date}: "
                    f"numbers={board.numbers}, pb={board.bonus_or_powerball}. Filtering."
                )
                collisions_count += 1
                continue

            if h in seen_in_batch:
                logger.warning(
                    f"Duplicate board collision within candidate batch for {raw_val}: "
                    f"numbers={board.numbers}, pb={board.bonus_or_powerball}. Filtering."
                )
                collisions_count += 1
                continue

            seen_in_batch.add(h)
            unique_boards.append(board)

        logger.info(
            f"Deduplication completed for {raw_val}: "
            f"{len(unique_boards)} unique boards retained, {collisions_count} collisions eliminated."
        )
        return unique_boards, collisions_count
