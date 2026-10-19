"""Statistical analyzer engine performing mathematical pre-processing on historical draws.

Executes purely locally in Python before any LLM invocations to minimize token consumption
and maximize predictive grounding.
"""
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from app.models.draw import Draw
from app.schemas.enums import GAME_RULES, GameType
from app.schemas.stats import (
    ConsecutivePair,
    LLMPromptContext,
    NumberDelay,
    NumberFrequency,
    OddEvenDistribution,
    StatisticalAnalysisResponse,
)


def calculate_number_frequencies(
    draws: List[Draw], min_num: int, max_num: int
) -> Dict[int, int]:
    """Computes exact occurrence counts for every possible number in the game matrix."""
    counts = {n: 0 for n in range(min_num, max_num + 1)}
    for draw in draws:
        for num in draw.numbers:
            if min_num <= num <= max_num:
                counts[num] += 1
    return counts


def get_hot_numbers(
    frequencies: Dict[int, int], total_draws: int, top_n: int = 10
) -> List[NumberFrequency]:
    """Identifies the top N most frequent numbers across historical draws."""
    if not frequencies or total_draws == 0:
        return []

    # Sort primarily by frequency desc, secondarily by number asc
    sorted_items = sorted(frequencies.items(), key=lambda x: (-x[1], x[0]))[:top_n]

    return [
        NumberFrequency(
            number=num,
            count=cnt,
            percentage=round((cnt / total_draws) * 100, 2),
        )
        for num, cnt in sorted_items
    ]


def get_cold_numbers(
    frequencies: Dict[int, int], total_draws: int, bottom_n: int = 10
) -> List[NumberFrequency]:
    """Identifies the bottom N least frequent numbers across historical draws."""
    if not frequencies or total_draws == 0:
        return []

    # Sort primarily by frequency asc, secondarily by number asc
    sorted_items = sorted(frequencies.items(), key=lambda x: (x[1], x[0]))[:bottom_n]

    return [
        NumberFrequency(
            number=num,
            count=cnt,
            percentage=round((cnt / total_draws) * 100, 2),
        )
        for num, cnt in sorted_items
    ]


def calculate_odd_even_ratios(
    draws: List[Draw],
) -> Tuple[List[OddEvenDistribution], str]:
    """Calculates odd/even parity ratios across all draws and finds the modal ratio."""
    if not draws:
        return [], "3:3"

    ratio_counter: Counter[str] = Counter()

    for draw in draws:
        odd_count = sum(1 for n in draw.numbers if n % 2 != 0)
        even_count = sum(1 for n in draw.numbers if n % 2 == 0)
        ratio_key = f"{odd_count}:{even_count}"
        ratio_counter[ratio_key] += 1

    total = len(draws)
    distributions: List[OddEvenDistribution] = []

    # Sort by count desc, then ratio string asc
    for ratio, cnt in sorted(ratio_counter.items(), key=lambda x: (-x[1], x[0])):
        distributions.append(
            OddEvenDistribution(
                ratio=ratio,
                count=cnt,
                percentage=round((cnt / total) * 100, 2),
            )
        )

    most_frequent = distributions[0].ratio if distributions else "3:3"
    return distributions, most_frequent


def calculate_consecutive_pairs(
    draws: List[Draw], min_count: int = 1
) -> List[ConsecutivePair]:
    """Identifies recurring adjacent numerical pairs (e.g. 14 and 15) appearing within the same draw."""
    if not draws:
        return []

    pair_counter: Counter[Tuple[int, int]] = Counter()

    for draw in draws:
        sorted_nums = sorted(draw.numbers)
        for i in range(len(sorted_nums) - 1):
            if sorted_nums[i + 1] == sorted_nums[i] + 1:
                pair_counter[(sorted_nums[i], sorted_nums[i + 1])] += 1

    pairs: List[ConsecutivePair] = []
    for pair_tuple, cnt in sorted(pair_counter.items(), key=lambda x: (-x[1], x[0])):
        if cnt >= min_count:
            pairs.append(ConsecutivePair(pair=list(pair_tuple), count=cnt))

    return pairs


def calculate_overdue_numbers(
    draws: List[Draw], min_num: int, max_num: int, top_n: int = 10
) -> List[NumberDelay]:
    """Calculates the absence span (draws since last drawn) for each number in the matrix.

    Draws are expected to be ordered chronologically descending (index 0 is latest).
    """
    if not draws:
        return [
            NumberDelay(number=n, draws_since_last=0)
            for n in range(min_num, min(min_num + top_n, max_num + 1))
        ]

    # Ensure chronological descending order
    sorted_draws = sorted(
        draws, key=lambda d: (d.draw_date, d.draw_number), reverse=True
    )
    total_draws = len(sorted_draws)

    delay_map: Dict[int, int] = {}

    for num in range(min_num, max_num + 1):
        found = False
        for idx, draw in enumerate(sorted_draws):
            if num in draw.numbers:
                delay_map[num] = idx
                found = True
                break
        if not found:
            delay_map[num] = total_draws

    # Sort primarily by draws_since_last desc (most overdue first), then number asc
    sorted_delays = sorted(delay_map.items(), key=lambda x: (-x[1], x[0]))[:top_n]

    return [
        NumberDelay(number=num, draws_since_last=delay)
        for num, delay in sorted_delays
    ]


def calculate_special_ball_stats(
    draws: List[Draw], game_type: GameType
) -> Optional[Dict[str, Any]]:
    """Calculates frequency distribution and hot/cold stats for bonus ball or Powerball."""
    if not draws:
        return None

    rules = GAME_RULES.get(game_type, {})
    total = len(draws)

    if rules.get("has_powerball"):
        pb_min = rules.get("powerball_min", 1)
        pb_max = rules.get("powerball_max", 20)
        pb_counts = {n: 0 for n in range(pb_min, pb_max + 1)}

        for d in draws:
            if d.powerball is not None and pb_min <= d.powerball <= pb_max:
                pb_counts[d.powerball] += 1

        hot_pb = sorted(pb_counts.items(), key=lambda x: (-x[1], x[0]))[:5]
        cold_pb = sorted(pb_counts.items(), key=lambda x: (x[1], x[0]))[:5]

        return {
            "type": "powerball",
            "hot_powerballs": [
                {"number": num, "count": cnt, "percentage": round((cnt / total) * 100, 2)}
                for num, cnt in hot_pb
            ],
            "cold_powerballs": [
                {"number": num, "count": cnt, "percentage": round((cnt / total) * 100, 2)}
                for num, cnt in cold_pb
            ],
        }

    if rules.get("has_bonus"):
        bonus_counts: Counter[int] = Counter()
        for d in draws:
            if d.bonus_ball is not None:
                bonus_counts[d.bonus_ball] += 1

        hot_bonus = sorted(bonus_counts.items(), key=lambda x: (-x[1], x[0]))[:5]

        return {
            "type": "bonus_ball",
            "hot_bonus_balls": [
                {"number": num, "count": cnt, "percentage": round((cnt / total) * 100, 2)}
                for num, cnt in hot_bonus
            ],
        }

    return None


def generate_statistical_summary(
    draws: List[Draw], game_type: GameType
) -> StatisticalAnalysisResponse:
    """Combines all pre-processing calculations into a unified response

    including optimized variables formatted for Qwen-Max prompt templates.
    """
    rules = GAME_RULES.get(game_type, {})
    min_num = rules.get("main_number_min", 1)
    max_num = rules.get("main_number_max", 52)

    total_draws = len(draws)
    frequencies = calculate_number_frequencies(draws, min_num, max_num)

    hot_numbers = get_hot_numbers(frequencies, total_draws, top_n=10)
    cold_numbers = get_cold_numbers(frequencies, total_draws, bottom_n=10)
    odd_even_ratios, most_frequent_ratio = calculate_odd_even_ratios(draws)
    consecutive_pairs = calculate_consecutive_pairs(draws, min_count=1)
    overdue_numbers = calculate_overdue_numbers(draws, min_num, max_num, top_n=10)
    special_stats = calculate_special_ball_stats(draws, game_type)

    date_range_start = min(d.draw_date for d in draws) if draws else None
    date_range_end = max(d.draw_date for d in draws) if draws else None

    # Pre-format LLM prompt context to eliminate downstream token overhead
    prompt_context = LLMPromptContext(
        hot_numbers=[n.number for n in hot_numbers],
        cold_numbers=[n.number for n in cold_numbers],
        odd_even_ratio=most_frequent_ratio,
        consecutive_pairs=[p.pair for p in consecutive_pairs[:5]],
        overdue_numbers=[o.number for o in overdue_numbers],
    )

    return StatisticalAnalysisResponse(
        game_type=game_type,
        sample_size=total_draws,
        date_range_start=date_range_start,
        date_range_end=date_range_end,
        hot_numbers=hot_numbers,
        cold_numbers=cold_numbers,
        overdue_numbers=overdue_numbers,
        odd_even_ratios=odd_even_ratios,
        most_frequent_odd_even_ratio=most_frequent_ratio,
        consecutive_pairs=consecutive_pairs,
        special_ball_stats=special_stats,
        llm_prompt_context=prompt_context,
    )
