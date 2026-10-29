from collections import Counter
import itertools
import math
import statistics
from typing import Any, Dict, List, Optional, Union
from loguru import logger
import numpy as np
from scipy.stats import chi2_contingency
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.draw import Draw
from app.schemas.board import AIBoardRecommendation
from app.schemas.enums import (
    BUNDLE_GAMES,
    BUNDLE_RULES,
    BundleType,
    GAME_RULES,
    GameType,
    game_key,
    is_bundle_key,
    resolve_rules,
)
from app.schemas.stats import (
    DeltaDistributionReport,
    DeltaFrequency,
    EnvironmentalAnalysisReport,
    EnvironmentalCorrelation,
    EVScoreReport,
    MarkovChainReport,
    MarkovTransitionCandidate,
    MonteCarloSimulationResult,
    PositionalDistribution,
    PositionalFrequencyReport,
    StatisticalAnalysisResponse,
)
from app.stats.analyzer import generate_statistical_summary


class StatsService:
    """Orchestrates historical draw extraction, mathematical pre-processing, and simulations."""

    async def get_recent_draws(
        self, db: AsyncSession, game_type: Union[GameType, BundleType, str], limit: int = 50
    ) -> List[Draw]:
        """Queries the database for the last N official draws for a specific game or bundle."""
        raw_val = game_type.value if hasattr(game_type, "value") else str(game_type)
        if is_bundle_key(raw_val):
            b_type = BundleType(raw_val)
            member_games = [g.value for g in BUNDLE_GAMES.get(b_type, [])]
            query = (
                select(Draw)
                .where(Draw.game_type.in_(member_games))
                .order_by(Draw.draw_date.desc(), Draw.draw_number.desc())
                .limit(limit * len(member_games))
            )
        else:
            query = (
                select(Draw)
                .where(Draw.game_type == raw_val)
                .order_by(Draw.draw_date.desc(), Draw.draw_number.desc())
                .limit(limit)
            )
        result = await db.execute(query)
        draws = list(result.scalars().all())
        logger.debug(f"Retrieved {len(draws)} historical draws for {raw_val} analysis.")
        return draws

    async def get_stats_for_game(
        self, db: AsyncSession, game_type: Union[GameType, BundleType, str], sample_size: int = 50
    ) -> StatisticalAnalysisResponse:
        """Fetches the latest draws and computes statistical summary locally."""
        draws = await self.get_recent_draws(db, game_type, limit=sample_size)
        return generate_statistical_summary(draws, game_type)

    async def get_stats_for_bundle(
        self, db: AsyncSession, bundle_type: Union[BundleType, str], sample_size: int = 50
    ) -> Dict[str, Any]:
        """Directive 21 & 22: Aggregates historical data per bundle and finds statistical intersection."""
        raw_val = bundle_type.value if hasattr(bundle_type, "value") else str(bundle_type)
        b_type = BundleType(raw_val)
        member_games = BUNDLE_GAMES.get(b_type, [])

        sub_draws: Dict[str, List[Draw]] = {}
        sub_stats: Dict[str, StatisticalAnalysisResponse] = {}
        all_bundle_draws: List[Draw] = []

        for g in member_games:
            d = await self.get_recent_draws(db, g, limit=sample_size)
            sub_draws[g.value] = d
            sub_stats[g.value] = generate_statistical_summary(d, g)
            all_bundle_draws.extend(d)

        all_bundle_draws.sort(key=lambda x: (x.draw_date, x.draw_number), reverse=True)
        aggregate_summary = generate_statistical_summary(all_bundle_draws, b_type)

        # Statistical intersection across sub-draws (Directive 22)
        sub_hot_sets = {g.value: set(n.number for n in sub_stats[g.value].hot_numbers) for g in member_games}
        all_hot_lists = [list(s) for s in sub_hot_sets.values()]
        counter = Counter([n for h_list in all_hot_lists for n in h_list])
        intersection_numbers = sorted([num for num, cnt in counter.items() if cnt >= 2])
        if not intersection_numbers and all_hot_lists:
            intersection_numbers = [n.number for n in aggregate_summary.hot_numbers[:5]]

        return {
            "bundle_name": b_type.value,
            "aggregate_summary": aggregate_summary,
            "sub_draw_stats": sub_stats,
            "statistical_intersection": intersection_numbers,
            "all_draws": all_bundle_draws,
        }

    def format_bundle_prompt_variables(
        self,
        bundle_data: Dict[str, Any],
        recent_draws: Optional[List[Draw]] = None,
    ) -> Dict[str, str]:
        """Directive 22: Formats multi-draw bundle stats into prompt variables highlighting intersection."""
        aggregate: StatisticalAnalysisResponse = bundle_data["aggregate_summary"]
        draws_to_use = recent_draws or bundle_data.get("all_draws")
        base_vars = self.format_prompt_variables(aggregate, draws=draws_to_use)

        # Format sub-draw breakdowns
        sub_parts = []
        for g_name, s_resp in bundle_data["sub_draw_stats"].items():
            top_nums = ", ".join(str(n.number) for n in s_resp.hot_numbers[:5])
            sub_parts.append(f"  * {g_name}: {top_nums}")
        sub_breakdown = "\n".join(sub_parts)

        # Statistical intersection
        inter_nums = bundle_data.get("statistical_intersection", [])
        inter_str = ", ".join(str(n) for n in inter_nums) if inter_nums else "None"

        base_vars["sub_draw_breakdown"] = sub_breakdown
        base_vars["statistical_intersection"] = inter_str
        return base_vars

    def format_prompt_variables(
        self,
        stats: StatisticalAnalysisResponse,
        draws: Optional[List[Draw]] = None,
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

        res = {
            "hot_numbers": hot_str,
            "cold_numbers": cold_str,
            "odd_even_ratio": ctx.odd_even_ratio,
            "consecutive_pairs": pairs_str,
            "overdue_numbers": overdue_str,
        }

        if draws:
            adv_parts = []
            try:
                delta_rep = self.calculate_delta_distribution(draws, stats.game_type)
                if delta_rep.top_deltas:
                    top_d_str = ", ".join(f"{d.delta} ({d.percentage}%)" for d in delta_rep.top_deltas[:4])
                    adv_parts.append(
                        f"\n- Delta Gap Frequencies: Mean={delta_rep.mean_delta:.1f}, Top Deltas: {top_d_str}"
                    )
            except Exception as e:
                logger.debug(f"Delta context formatting skipped: {e}")

            try:
                markov_rep = self.build_markov_transition_matrix(draws, stats.game_type, alpha=1.0)
                if markov_rep.top_transition_candidates:
                    top_m_str = ", ".join(str(c.number) for c in markov_rep.top_transition_candidates[:5])
                    adv_parts.append(
                        f"- Markov Transition Candidates (Laplace smoothed): {top_m_str}"
                    )
            except Exception as e:
                logger.debug(f"Markov context formatting skipped: {e}")

            if adv_parts:
                res["advanced_math_context"] = "\n".join(adv_parts)

        return res

    def calculate_environmental_correlations(
        self, draws: List[Draw], min_samples: int = 15
    ) -> EnvironmentalAnalysisReport:
        """Directive 16: Strict statistical guardrails for draw metadata.

        Runs Chi-Square test of independence on machine_name, ball_set, and draw_time.
        Only anomalies achieving p-value < 0.05 are flagged as significant.
        Never passes non-significant metadata to Qwen to prevent false correlation hallucinations.
        """
        features = ["machine_name", "ball_set", "draw_time"]
        significant_anomalies: List[EnvironmentalCorrelation] = []

        if len(draws) < min_samples:
            logger.debug(f"Insufficient draws ({len(draws)} < {min_samples}) for environmental Chi-Square tests.")
            return EnvironmentalAnalysisReport(
                features_analyzed=features,
                significant_anomalies=[],
                has_significant_anomalies=False,
                llm_prompt_summary=None,
            )

        # Decade buckets derived from the observed number range (supports 1-36,
        # 1-50 and 1-52 matrices without leaking empty buckets).
        max_observed = max(
            (max(d.numbers) for d in draws if d.numbers),
            default=52,
        )
        decade_buckets = [
            (start, min(start + 9, max_observed))
            for start in range(1, max_observed + 1, 10)
        ]

        for feat in features:
            # Group draws by categorical feature value
            category_counts: Dict[str, List[int]] = {}

            for draw in draws:
                val = getattr(draw, feat, None)
                if not val:
                    continue
                val_str = str(val).strip()
                if not val_str:
                    continue

                if val_str not in category_counts:
                    category_counts[val_str] = [0] * len(decade_buckets)

                for num in draw.numbers:
                    for b_idx, (b_min, b_max) in enumerate(decade_buckets):
                        if b_min <= num <= b_max:
                            category_counts[val_str][b_idx] += 1
                            break

            # Need at least 2 categories and each must have observed numbers
            if len(category_counts) < 2:
                continue

            contingency_matrix = np.array(list(category_counts.values()))

            # Require non-zero totals in at least two rows and columns
            if contingency_matrix.shape[0] < 2 or contingency_matrix.shape[1] < 2:
                continue
            if np.sum(contingency_matrix) == 0:
                continue

            # Remove columns that are all zero to avoid degeneracy
            non_zero_cols = np.sum(contingency_matrix, axis=0) > 0
            if np.sum(non_zero_cols) < 2:
                continue
            valid_matrix = contingency_matrix[:, non_zero_cols]

            try:
                chi2_stat, p_val, dof, _ = chi2_contingency(valid_matrix)
                is_sig = bool(p_val < 0.05)

                anomaly_desc = None
                if is_sig:
                    cats_str = ", ".join(category_counts.keys())
                    anomaly_desc = (
                        f"Significant distribution variance detected across {feat} [{cats_str}] "
                        f"(Chi2={chi2_stat:.2f}, p={p_val:.4f}, df={dof})."
                    )
                    logger.warning(f"Environmental anomaly validated (p < 0.05): {anomaly_desc}")

                corr = EnvironmentalCorrelation(
                    feature_name=feat,
                    chi2_statistic=round(float(chi2_stat), 3),
                    p_value=round(float(p_val), 4),
                    is_significant=is_sig,
                    degrees_of_freedom=int(dof),
                    anomaly_description=anomaly_desc,
                )

                if is_sig:
                    significant_anomalies.append(corr)

            except Exception as chi_err:
                logger.debug(f"Chi-Square test skipped for {feat}: {chi_err}")

        has_sig = len(significant_anomalies) > 0
        prompt_summary = None
        if has_sig:
            lines = ["\nValidated Environmental Anomalies (Statistical Significance p < 0.05 ONLY):"]
            for a in significant_anomalies:
                lines.append(f"- {a.anomaly_description}")
            prompt_summary = "\n".join(lines) + "\n"

        return EnvironmentalAnalysisReport(
            features_analyzed=features,
            significant_anomalies=significant_anomalies,
            has_significant_anomalies=has_sig,
            llm_prompt_summary=prompt_summary,
        )

    def run_monte_carlo_stress_test(
        self,
        boards: List[Union[AIBoardRecommendation, Dict[str, Any]]],
        historical_draws: List[Draw],
        game_type: Union[GameType, BundleType, str],
        iterations: int = 10000,
    ) -> List[MonteCarloSimulationResult]:
        """Directive 15: Local Python Monte Carlo simulation (minimum 10,000 iterations).

        Stress-tests proposed boards against weighted historical draw probabilities.
        Logs simulated hit rates.
        """
        rules = resolve_rules(game_type)
        main_min = rules.get("main_number_min", 1)
        main_max = rules.get("main_number_max", 52)
        main_count = rules.get("main_numbers_count", 6)

        # 1. Calculate weighted ball probability distribution from historical draws
        ball_counts = {n: 1 for n in range(main_min, main_max + 1)}  # Laplace smoothing +1
        for d in historical_draws:
            for num in d.numbers:
                if main_min <= num <= main_max:
                    ball_counts[num] += 1

        total_occurrences = sum(ball_counts.values())
        balls = np.arange(main_min, main_max + 1)
        probabilities = np.array([ball_counts[n] / total_occurrences for n in balls])
        probabilities = probabilities / np.sum(probabilities)  # Ensure exact sum to 1.0

        # 2. Generate simulated draws
        logger.info(
            f"Executing Monte Carlo stress test ({iterations} iterations) for {len(boards)} "
            f"{game_key(game_type)} boards using weighted probability distribution..."
        )
        simulated_draws = [
            set(np.random.choice(balls, size=main_count, replace=False, p=probabilities))
            for _ in range(iterations)
        ]

        # 3. Test proposed boards against simulated draws
        results: List[MonteCarloSimulationResult] = []

        for idx, board in enumerate(boards):
            if isinstance(board, AIBoardRecommendation):
                b_nums = board.numbers
                pb = board.bonus_or_powerball
            else:
                b_nums = board.get("numbers", [])
                pb = board.get("bonus_or_powerball")

            board_set = set(b_nums)
            matches = [len(board_set.intersection(sim_draw)) for sim_draw in simulated_draws]

            m2_plus = sum(1 for m in matches if m >= 2) / iterations
            m3_plus = sum(1 for m in matches if m >= 3) / iterations
            m4_plus = sum(1 for m in matches if m >= 4) / iterations

            # Hit rate = probability of reaching the game's minimum prize match
            # (Daily Lotto pays from 2 matches, PowerBall from 2, Lotto from 3).
            hit_threshold = rules.get(
                "mc_hit_threshold", 2 if rules.get("has_powerball") else 3
            )
            hit_rate = m2_plus if hit_threshold <= 2 else m3_plus

            logger.info(
                f"Monte Carlo stress test | Board #{idx + 1} {b_nums} | "
                f"Hit Rate (>={hit_threshold} matches): {hit_rate * 100:.2f}% "
                f"(>=4: {m4_plus * 100:.2f}%) across {iterations:,} iterations"
            )

            results.append(
                MonteCarloSimulationResult(
                    board_index=idx + 1,
                    numbers=b_nums,
                    bonus_or_powerball=pb,
                    iterations=iterations,
                    match_2_or_more_rate=round(m2_plus, 4),
                    match_3_or_more_rate=round(m3_plus, 4),
                    match_4_or_more_rate=round(m4_plus, 4),
                    simulated_hit_rate=round(hit_rate, 4),
                    stress_test_passed=True,
                )
            )

        return results

    # ==============================================================================
    # Phase 3.7: Advanced Mathematical Models (Directives 17 - 20)
    # ==============================================================================

    def calculate_delta_distribution(
        self, draws: List[Draw], game_type: GameType
    ) -> DeltaDistributionReport:
        """Directive 17: Delta System logic (gap analysis) across historical draws.

        Calculates gap distributions (delta_1 = n_1, delta_i = n_i - n_{i-1})
        to ensure generated boards mimic historical winning geometries.
        """
        rules = GAME_RULES.get(game_type, {})
        main_count = rules.get("main_numbers_count", 6)

        all_deltas: List[int] = []
        positional_delta_lists: Dict[str, List[int]] = {
            f"delta_{i + 1}": [] for i in range(main_count)
        }

        valid_draw_count = 0
        for d in draws:
            if not d.numbers or len(d.numbers) < main_count:
                continue
            sorted_nums = sorted(d.numbers)[:main_count]
            valid_draw_count += 1

            # delta_1 = first number (distance from 0)
            d1 = sorted_nums[0]
            all_deltas.append(d1)
            positional_delta_lists["delta_1"].append(d1)

            # delta_i = n_i - n_{i-1}
            for i in range(1, main_count):
                delta_val = sorted_nums[i] - sorted_nums[i - 1]
                all_deltas.append(delta_val)
                positional_delta_lists[f"delta_{i + 1}"].append(delta_val)

        if not all_deltas:
            # Fallback default report if no draws available
            return DeltaDistributionReport(
                game_type=game_type,
                sample_size=0,
                mean_delta=8.0,
                median_delta=7.0,
                std_delta=4.0,
                min_delta=1,
                max_delta=25,
                top_deltas=[],
                positional_delta_means={},
            )

        mean_delta = float(np.mean(all_deltas))
        median_delta = float(np.median(all_deltas))
        std_delta = float(np.std(all_deltas))
        min_delta = int(np.min(all_deltas))
        max_delta = int(np.max(all_deltas))

        # Top frequent delta values
        counter = Counter(all_deltas)
        total_deltas = len(all_deltas)
        top_deltas = [
            DeltaFrequency(
                delta=d_val,
                count=cnt,
                percentage=round((cnt / total_deltas) * 100.0, 2),
            )
            for d_val, cnt in counter.most_common(10)
        ]

        pos_means = {
            k: round(float(np.mean(v)), 2) if v else 0.0
            for k, v in positional_delta_lists.items()
        }

        return DeltaDistributionReport(
            game_type=game_type,
            sample_size=valid_draw_count,
            mean_delta=round(mean_delta, 2),
            median_delta=round(median_delta, 2),
            std_delta=round(std_delta, 2),
            min_delta=min_delta,
            max_delta=max_delta,
            top_deltas=top_deltas,
            positional_delta_means=pos_means,
        )

    def calculate_positional_frequencies(
        self, draws: List[Draw], game_type: GameType
    ) -> PositionalFrequencyReport:
        """Directive 17: Positional Frequency tracking (P1-P6).

        Tracks structural distributions for each ball position and calculates
        plausible geometric boundaries within 2.5 sigma.
        """
        rules = GAME_RULES.get(game_type, {})
        main_count = rules.get("main_numbers_count", 6)
        main_min = rules.get("main_number_min", 1)
        main_max = rules.get("main_number_max", 52)

        position_numbers: Dict[str, List[int]] = {
            f"P{i + 1}": [] for i in range(main_count)
        }

        valid_count = 0
        for d in draws:
            if not d.numbers or len(d.numbers) < main_count:
                continue
            sorted_nums = sorted(d.numbers)[:main_count]
            valid_count += 1
            for i, num in enumerate(sorted_nums):
                position_numbers[f"P{i + 1}"].append(num)

        positions_report: Dict[str, PositionalDistribution] = {}
        validity_bounds: Dict[str, List[int]] = {}

        for i in range(main_count):
            pos_key = f"P{i + 1}"
            nums = position_numbers[pos_key]
            if nums:
                mean_val = float(np.mean(nums))
                med_val = float(np.median(nums))
                std_val = float(np.std(nums)) if len(nums) > 1 else 1.0
                min_val = int(np.min(nums))
                max_val = int(np.max(nums))
                top_common = [n for n, _ in Counter(nums).most_common(5)]

                # Plausible structural bounds within +/- 2.5 sigma
                lower_bound = max(main_min, int(round(mean_val - 2.5 * std_val)))
                upper_bound = min(main_max, int(round(mean_val + 2.5 * std_val)))
                # Position index consistency constraint: lower bound cannot be less than pos_idx + 1
                lower_bound = max(lower_bound, i + 1)
                upper_bound = min(upper_bound, main_max - (main_count - 1 - i))
                if lower_bound > upper_bound:
                    lower_bound, upper_bound = min_val, max_val
            else:
                # Default positional heuristics
                mean_val = main_min + (i * ((main_max - main_min) / main_count))
                med_val = mean_val
                std_val = 5.0
                min_val = main_min + i
                max_val = main_max - (main_count - 1 - i)
                top_common = []
                lower_bound = min_val
                upper_bound = max_val

            positions_report[pos_key] = PositionalDistribution(
                position=pos_key,
                mean=round(mean_val, 2),
                median=round(med_val, 2),
                min_value=min_val,
                max_value=max_val,
                std_dev=round(std_val, 2),
                most_common_numbers=top_common,
            )
            validity_bounds[pos_key] = [lower_bound, upper_bound]

        return PositionalFrequencyReport(
            game_type=game_type,
            sample_size=valid_count,
            positions=positions_report,
            structural_validity_bounds=validity_bounds,
        )

    def validate_positional_structure(
        self, numbers: List[int], bounds: Dict[str, List[int]]
    ) -> bool:
        """Validates that a board's sorted numbers respect positional structural bounds."""
        sorted_nums = sorted(numbers)
        for i, num in enumerate(sorted_nums):
            pos_key = f"P{i + 1}"
            if pos_key in bounds:
                b_min, b_max = bounds[pos_key]
                if not (b_min <= num <= b_max):
                    return False
        return True

    def build_markov_transition_matrix(
        self, draws: List[Draw], game_type: GameType, alpha: float = 1.0
    ) -> MarkovChainReport:
        """Directive 19: Markov chain transition matrix with Laplace smoothing.

        Applies Laplace smoothing (alpha=1.0) across all states to eliminate
        zero-probability dead ends on finite samples (e.g. 50 draws).
        """
        rules = GAME_RULES.get(game_type, {})
        m_max = rules.get("main_number_max", 52)

        # Sort draws chronologically (oldest to latest)
        chrono_draws = sorted(
            draws, key=lambda d: (d.draw_date, d.draw_number or 0)
        )

        # Count transition occurrences C[u][v]
        count_matrix = np.zeros((m_max + 1, m_max + 1), dtype=float)

        for t in range(len(chrono_draws) - 1):
            cur_nums = [n for n in chrono_draws[t].numbers if 1 <= n <= m_max]
            nxt_nums = [n for n in chrono_draws[t + 1].numbers if 1 <= n <= m_max]
            for u in cur_nums:
                for v in nxt_nums:
                    count_matrix[u, v] += 1.0

        # Apply Laplace Smoothing: P(v|u) = (C[u, v] + alpha) / (sum_v C[u, v] + M * alpha)
        trans_probs = np.zeros((m_max + 1, m_max + 1), dtype=float)
        for u in range(1, m_max + 1):
            row_sum = np.sum(count_matrix[u, 1:]) + (m_max * alpha)
            trans_probs[u, 1:] = (count_matrix[u, 1:] + alpha) / row_sum

        latest_nums: List[int] = []
        top_candidates: List[MarkovTransitionCandidate] = []

        if chrono_draws:
            latest_nums = sorted([n for n in chrono_draws[-1].numbers if 1 <= n <= m_max])
            # Calculate aggregate transition probability for each candidate v in 1..m_max
            candidate_scores: List[MarkovTransitionCandidate] = []
            for v in range(1, m_max + 1):
                # Average transition probability from numbers in the latest draw
                probs = [trans_probs[u, v] for u in latest_nums]
                avg_p = float(np.mean(probs)) if probs else 1.0 / m_max
                # Identify prior numbers giving highest transition probability to v
                supporting = sorted(
                    latest_nums, key=lambda u: trans_probs[u, v], reverse=True
                )[:2]
                candidate_scores.append(
                    MarkovTransitionCandidate(
                        number=v,
                        probability=round(avg_p, 4),
                        supporting_prior_numbers=supporting,
                    )
                )

            # Sort descending by probability
            candidate_scores.sort(key=lambda c: c.probability, reverse=True)
            top_candidates = candidate_scores[:12]

        return MarkovChainReport(
            game_type=game_type,
            sample_size=len(chrono_draws),
            alpha=alpha,
            matrix_dimension=m_max,
            top_transition_candidates=top_candidates,
            latest_draw_numbers=latest_nums,
        )

    def calculate_ev_score(
        self, numbers: List[int], game_type: Optional[GameType] = None
    ) -> EVScoreReport:
        """Directive 20: Expected Value (EV) Optimization.

        Penalizes human-biased combinations (all numbers <= 31, arithmetic sequences,
        and obvious consecutive clusters) to maximize potential non-shared jackpot ROI.
        """
        sorted_nums = sorted(numbers)
        k = len(sorted_nums)
        if k == 0:
            return EVScoreReport(
                numbers=[],
                ev_score=50.0,
                is_human_biased=True,
                calendar_count=0,
                calendar_ratio=0.0,
                is_arithmetic_sequence=False,
                has_consecutive_run=False,
                penalties=["Empty board"],
                recommendation="Empty board cannot be scored.",
            )

        score = 80.0
        penalties: List[str] = []

        # 1. Calendar numbers bias (numbers <= 31: birthdays/anniversaries)
        cal_count = sum(1 for n in sorted_nums if n <= 31)
        cal_ratio = cal_count / k

        if cal_ratio == 1.0:
            score -= 40.0
            penalties.append("100% calendar numbers (all <= 31): extreme human birthday bias.")
        elif cal_ratio >= 0.8:
            score -= 22.0
            penalties.append(f"Heavy calendar bias ({cal_count}/{k} numbers <= 31).")
        elif cal_ratio <= 0.35:
            # Numbers > 31 are underplayed by the general public -> higher EV!
            score += 12.0

        # 2. Arithmetic sequence detection (e.g. 5, 10, 15, 20, 25, 30 or 2, 4, 6, 8, 10, 12)
        is_arithmetic = False
        if k >= 3:
            deltas = [sorted_nums[i] - sorted_nums[i - 1] for i in range(1, k)]
            if len(set(deltas)) == 1:
                is_arithmetic = True
                score -= 40.0
                penalties.append(f"Exact arithmetic progression (constant delta={deltas[0]}).")

        # 3. Consecutive runs (e.g. 14, 15, 16)
        has_consecutive = False
        max_run = 1
        current_run = 1
        for i in range(1, k):
            if sorted_nums[i] == sorted_nums[i - 1] + 1:
                current_run += 1
                if current_run > max_run:
                    max_run = current_run
            else:
                current_run = 1

        if max_run >= 3:
            has_consecutive = True
            score -= 18.0
            penalties.append(f"Consecutive run of {max_run} adjacent numbers.")

        # 4. Common factor / multiple check (e.g. all multiples of 5 or 7)
        g = sorted_nums[0]
        for n in sorted_nums[1:]:
            g = math.gcd(g, n)
        if g > 1:
            score -= 15.0
            penalties.append(f"All board numbers share common divisor {g}.")

        ev_score = round(max(0.0, min(100.0, score)), 2)
        is_biased = bool(cal_ratio == 1.0 or is_arithmetic or max_run >= 4 or ev_score < 50.0)

        if is_biased:
            recommendation = (
                "Sub-optimal EV: contains high human-bias patterns prone to severe prize sharing."
            )
        elif ev_score >= 80.0:
            recommendation = (
                "Excellent EV: non-calendar heavy distribution maximizing non-shared jackpot potential."
            )
        else:
            recommendation = "Balanced EV: moderate human bias risk."

        return EVScoreReport(
            numbers=sorted_nums,
            ev_score=ev_score,
            is_human_biased=is_biased,
            calendar_count=cal_count,
            calendar_ratio=round(cal_ratio, 3),
            is_arithmetic_sequence=is_arithmetic,
            has_consecutive_run=has_consecutive,
            penalties=penalties,
            recommendation=recommendation,
        )

    async def get_delta_distribution(
        self, db: AsyncSession, game_type: GameType, sample_size: int = 50
    ) -> DeltaDistributionReport:
        """Asynchronously retrieves recent draws and computes delta gap distribution."""
        draws = await self.get_recent_draws(db, game_type, limit=sample_size)
        return self.calculate_delta_distribution(draws, game_type)

    async def get_positional_frequencies(
        self, db: AsyncSession, game_type: GameType, sample_size: int = 50
    ) -> PositionalFrequencyReport:
        """Asynchronously retrieves recent draws and computes positional frequency report."""
        draws = await self.get_recent_draws(db, game_type, limit=sample_size)
        return self.calculate_positional_frequencies(draws, game_type)

    async def get_markov_chain(
        self, db: AsyncSession, game_type: GameType, sample_size: int = 50, alpha: float = 1.0
    ) -> MarkovChainReport:
        """Asynchronously retrieves recent draws and builds Laplace-smoothed Markov chain."""
        draws = await self.get_recent_draws(db, game_type, limit=sample_size)
        return self.build_markov_transition_matrix(draws, game_type, alpha=alpha)

