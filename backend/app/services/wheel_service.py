"""Combinatorial Abbreviated Wheeling Service.

Adheres to:
- Directive 18: Combinatorial Wheeling - Qwen/Stats outputs a high-confidence pool (10-14 numbers),
  and Python wheels them across allocated boards to guarantee maximum combinatorial coverage.
- Directive 20: Expected Value (EV) optimization - Filters out human-biased boards during wheeling.
"""
from itertools import combinations
import math
from typing import Any, Dict, List, Optional, Set, Tuple
from loguru import logger

from app.schemas.board import AIBoardRecommendation
from app.schemas.enums import GAME_RULES, GameType
from app.services.stats_service import StatsService


class WheelService:
    """Implements combinatorial abbreviated wheeling for lottery ticket generation."""

    def __init__(self):
        self.stats_service = StatsService()

    def wheel_candidate_pool(
        self,
        pool: List[int],
        board_count: int,
        game_type: GameType,
        bonus_or_powerball: Optional[int] = None,
        base_confidence: float = 85.0,
        custom_reasoning: Optional[str] = None,
    ) -> List[AIBoardRecommendation]:
        """Wheels an N-number pool into B boards with maximal pair coverage and EV filtering.

        Directive 18: Abbreviated Wheeling guarantees combinatorial coverage of the pool
        within the budget-constrained board count B.
        """
        rules = GAME_RULES.get(game_type, {})
        k = rules.get("main_numbers_count", 6)
        min_num = rules.get("main_number_min", 1)
        max_num = rules.get("main_number_max", 52)
        has_pb = rules.get("has_powerball", False)

        # 1. Clean and validate candidate pool
        clean_pool = sorted(list({int(n) for n in pool if min_num <= int(n) <= max_num}))

        if len(clean_pool) < k:
            logger.warning(
                f"Candidate pool size ({len(clean_pool)}) is smaller than required board size ({k}). "
                f"Auto-padding with non-calendar high numbers for {game_type.value}."
            )
            # Pad with numbers from max_num down
            pad_candidates = [n for n in range(max_num, min_num - 1, -1) if n not in clean_pool]
            clean_pool.extend(pad_candidates[: (k - len(clean_pool))])
            clean_pool.sort()

        # If board_count is 1, pick the combination with highest EV from the pool
        all_combos = list(combinations(clean_pool, k))

        # 2. Score each combination for Expected Value (Directive 20)
        scored_combos: List[Tuple[Tuple[int, ...], float, bool]] = []
        for combo in all_combos:
            combo_list = list(combo)
            ev_report = self.stats_service.calculate_ev_score(combo_list, game_type=game_type)
            scored_combos.append((combo, ev_report.ev_score, ev_report.is_human_biased))

        # Prefer non-human-biased combos; if none exist, use highest EV combos
        viable_combos = [c for c in scored_combos if not c[2]]
        if not viable_combos:
            viable_combos = sorted(scored_combos, key=lambda x: x[1], reverse=True)
        else:
            # Sort viable combos by EV score descending
            viable_combos.sort(key=lambda x: x[1], reverse=True)

        # 3. Maximal Pairwise Combinatorial Coverage Greedy Selection
        selected_combos: List[Tuple[int, ...]] = []
        covered_pairs: Set[Tuple[int, int]] = set()

        remaining_candidates = [c[0] for c in viable_combos]

        for _ in range(min(board_count, len(remaining_candidates))):
            best_combo = None
            max_new_pairs = -1

            for cand in remaining_candidates:
                cand_pairs = set(combinations(cand, 2))
                new_pairs_count = len(cand_pairs - covered_pairs)
                if new_pairs_count > max_new_pairs:
                    max_new_pairs = new_pairs_count
                    best_combo = cand

            if best_combo is None:
                best_combo = remaining_candidates[0]

            selected_combos.append(best_combo)
            covered_pairs.update(combinations(best_combo, 2))
            remaining_candidates.remove(best_combo)

        # If more boards were requested than combinations available, cycle or vary
        while len(selected_combos) < board_count and all_combos:
            for combo in all_combos:
                if combo not in selected_combos:
                    selected_combos.append(combo)
                    if len(selected_combos) == board_count:
                        break
            if len(selected_combos) < board_count:
                break

        # 4. Construct AIBoardRecommendation instances
        results: List[AIBoardRecommendation] = []
        total_possible_pairs = len(list(combinations(clean_pool, 2)))
        coverage_pct = (
            round((len(covered_pairs) / total_possible_pairs) * 100.0, 1)
            if total_possible_pairs > 0
            else 100.0
        )

        for idx, combo in enumerate(selected_combos, start=1):
            nums = sorted(list(combo))
            ev = self.stats_service.calculate_ev_score(nums, game_type=game_type)
            reasoning = (
                custom_reasoning
                or f"Combinatorial abbreviated wheel #{idx}/{len(selected_combos)} "
                f"from {len(clean_pool)}-number pool {clean_pool[:8]}... "
                f"(Coverage: {coverage_pct}% pairs, EV: {ev.ev_score:.1f}/100)"
            )

            # Assign Powerball if required
            pb = None
            if has_pb:
                pb = bonus_or_powerball or 8

            results.append(
                AIBoardRecommendation(
                    numbers=nums,
                    bonus_or_powerball=pb,
                    confidence_score=base_confidence,
                    reasoning=reasoning,
                )
            )

        logger.info(
            f"Wheeled pool of {len(clean_pool)} numbers into {len(results)} boards for {game_type.value} "
            f"with {coverage_pct}% pair coverage and EV filtering."
        )
        return results
