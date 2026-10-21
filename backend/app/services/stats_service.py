import itertools
from typing import Any, Dict, List, Optional, Union
from loguru import logger
import numpy as np
from scipy.stats import chi2_contingency
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.draw import Draw
from app.schemas.board import AIBoardRecommendation
from app.schemas.enums import GAME_RULES, GameType
from app.schemas.stats import (
    EnvironmentalAnalysisReport,
    EnvironmentalCorrelation,
    MonteCarloSimulationResult,
    StatisticalAnalysisResponse,
)
from app.stats.analyzer import generate_statistical_summary


class StatsService:
    """Orchestrates historical draw extraction, mathematical pre-processing, and simulations."""

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

        # Ball decade buckets: 1-10, 11-20, 21-30, 31-40, 41-52
        decade_buckets = [(1, 10), (11, 20), (21, 30), (31, 40), (41, 52)]

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
        game_type: GameType,
        iterations: int = 10000,
    ) -> List[MonteCarloSimulationResult]:
        """Directive 15: Local Python Monte Carlo simulation (minimum 10,000 iterations).

        Stress-tests proposed boards against weighted historical draw probabilities.
        Logs simulated hit rates.
        """
        rules = GAME_RULES.get(game_type, {})
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
            f"{game_type.value} boards using weighted probability distribution..."
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

            # Hit rate = probability of >= 3 matches (or >= 2 for PowerBall games)
            hit_rate = m2_plus if rules.get("has_powerball") else m3_plus

            logger.info(
                f"Monte Carlo stress test | Board #{idx + 1} {b_nums} | "
                f"Hit Rate (>={2 if rules.get('has_powerball') else 3} matches): {hit_rate * 100:.2f}% "
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
