"""Alibaba Cloud DashScope Qwen-Max AI integration service.

Adheres strictly to:
- Directive 1: API key loaded securely via Pydantic settings.
- Directive 2: Strict JSON enforcement with Pydantic schema validation.
- Directive 6: Retry logic using tenacity with exponential backoff.
- Directive 7: Isolated prompts imported directly from prompts.py.
"""
import asyncio
from datetime import date
from http import HTTPStatus
import json
import re
import secrets
from typing import Any, Dict, List, Optional, Union
from loguru import logger
import dashscope
from dashscope import Generation
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.models.analytics import TemporalAnalytics
from app.models.board import BoardResult, GeneratedBoard
from app.models.draw import Draw
from app.schemas.analytics import TemporalMetrics, TemporalPatternReviewResponse
from app.schemas.board import (
    AIBoardRecommendation,
    AIGenerationResponse,
    PostDrawFeedbackResponse,
)
from app.schemas.enums import BUNDLE_RULES, BundleType, GAME_RULES, GameType
from app.services.prompts import (
    MONTHLY_DEEP_DIVE_SYSTEM_PROMPT,
    MONTHLY_DEEP_DIVE_USER_PROMPT,
    POST_DRAW_FEEDBACK_SYSTEM_PROMPT,
    POST_DRAW_FEEDBACK_USER_PROMPT,
    PRIMARY_ANALYST_SYSTEM_PROMPT,
    PRIMARY_GENERATION_USER_PROMPT,
    WEEKLY_PATTERN_REVIEW_SYSTEM_PROMPT,
    WEEKLY_PATTERN_REVIEW_USER_PROMPT,
)


class AIServiceError(Exception):
    """Raised when DashScope interaction or JSON parsing fails."""
    pass


class AIService:
    """Orchestrates structured probabilistic analysis and generation via Qwen-Max."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        analytics_model: Optional[str] = None,
    ):
        self.api_key = api_key or settings.DASHSCOPE_API_KEY
        self.base_url = (base_url or settings.DASHSCOPE_BASE_URL).rstrip("/")
        self.model = model or settings.QWEN_MODEL or Generation.Models.qwen_max
        self.analytics_model = analytics_model or settings.QWEN_ANALYTICS_MODEL or "qwen3.8-flash"

    @staticmethod
    def clean_json_markdown(raw_text: str) -> str:
        """Strips markdown code blocks (```json ... ```) if present in raw LLM output."""
        text = raw_text.strip()
        if text.startswith("```"):
            # Remove leading ```json or ```
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            # Remove trailing ```
            text = re.sub(r"\s*```$", "", text)
        return text.strip()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((AIServiceError, Exception)),
        reraise=True,
    )
    async def call_qwen_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Queries Qwen expecting a strictly structured JSON response."""
        if not self.api_key:
            raise AIServiceError(
                "DashScope / Qwen API key is not configured. Set DASHSCOPE_API_KEY in .env."
            )

        active_model = model or self.model
        logger.debug(f"Dispatching structured query to Qwen ({active_model}) at {self.base_url}...")

        # If using OpenAI-compatible mode endpoint (e.g., https://maas.qwencloudapi.com/compatible-mode/v1)
        if "compatible-mode" in self.base_url or "chat/completions" in self.base_url or "qwencloudapi" in self.base_url:
            import httpx

            url = f"{self.base_url}/chat/completions" if not self.base_url.endswith("/chat/completions") else self.base_url
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": active_model,
                "messages": messages,
                "temperature": temperature,
            }

            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(url, headers=headers, json=payload)
            except Exception as net_err:
                logger.error(f"Network error communicating with Qwen API at {url}: {net_err}")
                raise AIServiceError(f"Network error contacting Qwen endpoint: {net_err}")

            if resp.status_code != 200:
                logger.error(f"Qwen API error [{resp.status_code}]: {resp.text}")
                raise AIServiceError(f"Qwen API error [{resp.status_code}]: {resp.text}")

            resp_data = resp.json()
            try:
                raw_content = resp_data["choices"][0]["message"]["content"]
            except (KeyError, IndexError) as parse_err:
                logger.error(f"Malformed response format from Qwen API: {resp_data}")
                raise AIServiceError(f"Malformed response format: {parse_err}")

        else:
            # Fallback to DashScope SDK Generation.call
            def _blocking_call():
                return Generation.call(
                    model=active_model,
                    messages=messages,
                    result_format="message",
                    temperature=temperature,
                    api_key=self.api_key,
                )

            response = await asyncio.to_thread(_blocking_call)

            if response.status_code != HTTPStatus.OK:
                err_code = getattr(response, "code", "UNKNOWN_ERROR")
                err_msg = getattr(response, "message", "No error message provided")
                logger.error(f"DashScope Qwen error [{response.status_code}]: {err_code} - {err_msg}")
                raise AIServiceError(f"DashScope API call failed: {err_code} - {err_msg}")

            try:
                raw_content = response.output.choices[0].message.content
            except (AttributeError, IndexError) as exc:
                logger.error(f"Unexpected response structure from DashScope: {response}")
                raise AIServiceError(f"Malformed response structure from DashScope: {exc}")

        cleaned_json = self.clean_json_markdown(raw_content)

        try:
            parsed_dict = json.loads(cleaned_json)
        except json.JSONDecodeError as decode_err:
            logger.error(f"Failed to decode Qwen JSON response: {decode_err}\nRaw: {raw_content}")
            raise AIServiceError(f"Invalid JSON returned by Qwen-Max: {decode_err}")

        return parsed_dict

    async def generate_boards(
        self,
        game_type: Union[GameType, BundleType, str],
        target_draw_date: date,
        allocated_boards: int,
        stats_context: Dict[str, Any],
        temporal_bias: Optional[Dict[str, Any]] = None,
        environmental_anomalies: Optional[str] = None,
        historical_draws: Optional[List[Draw]] = None,
        fallback_on_error: bool = True,
    ) -> AIGenerationResponse:
        """Prompts Qwen-Max using isolated templates and validates output with Pydantic.

        Directive 13: Graceful degradation - If Qwen-Max fails or returns invalid JSON
        after 3 retries, falls back to deterministic statistical generation, and if that
        fails, to secrets cryptographically random generation.
        """
        raw_key = game_type.value if hasattr(game_type, "value") else str(game_type)
        logger.info(
            f"Invoking Qwen-Max generation for {raw_key} on {target_draw_date} "
            f"({allocated_boards} boards requested)"
        )

        if raw_key in ("LOTTO_FAMILY", "POWERBALL_FAMILY"):
            rules = BUNDLE_RULES.get(BundleType(raw_key), {})
        else:
            rules = GAME_RULES.get(game_type, {})

        if rules.get("has_powerball"):
            rules_summary = (
                f"Pick exactly {rules['main_numbers_count']} main numbers (range {rules['main_number_min']}-{rules['main_number_max']}) "
                f"and 1 Powerball (range {rules['powerball_min']}-{rules['powerball_max']})."
            )
        else:
            rules_summary = (
                f"Pick exactly {rules['main_numbers_count']} main numbers (range {rules['main_number_min']}-{rules['main_number_max']}). "
                f"bonus_or_powerball must be null."
            )

        # Build temporal bias context if present
        bias_payload = temporal_bias or stats_context.get("temporal_bias")
        if bias_payload and isinstance(bias_payload, dict):
            bias_parts = ["\nTemporal Analytics Bias (Weekly/Monthly Insights):"]
            sum_rng = bias_payload.get("suggested_sum_range")
            if sum_rng:
                bias_parts.append(f"- Suggested Sum Range: {sum_rng[0]} - {sum_rng[1]}")
            favored_parity = bias_payload.get("favored_parity")
            if favored_parity:
                bias_parts.append(f"- Favored Parity Ratio: {favored_parity}")
            boost = bias_payload.get("boost_numbers")
            if boost:
                bias_parts.append(f"- Momentum Boost Numbers: {', '.join(str(n) for n in boost)}")
            dampen = bias_payload.get("dampen_numbers")
            if dampen:
                bias_parts.append(f"- Dampened Stagnant Numbers: {', '.join(str(n) for n in dampen)}")
            temporal_bias_context = "\n".join(bias_parts) + "\n"
        else:
            temporal_bias_context = ""

        # Directive 16: Conditionally append environmental anomalies ONLY if p < 0.05
        env_context = environmental_anomalies or stats_context.get("environmental_anomalies") or ""

        adv_math = stats_context.get("advanced_math_context", "")

        # Directive 22: Append bundle intersection context if available
        inter_parts = []
        if stats_context.get("sub_draw_breakdown"):
            inter_parts.append(f"\n- Sub-Draw Hot Candidates Breakdown:\n{stats_context['sub_draw_breakdown']}")
        if stats_context.get("statistical_intersection"):
            inter_parts.append(f"- Bundle Statistical Intersection (Shared Candidates): {stats_context['statistical_intersection']}")
        bundle_inter_ctx = "\n".join(inter_parts)

        user_content = PRIMARY_GENERATION_USER_PROMPT.format(
            game_type=raw_key,
            target_draw_date=target_draw_date.isoformat(),
            allocated_boards=allocated_boards,
            game_matrix_rules=rules_summary,
            hot_numbers=stats_context.get("hot_numbers", "None"),
            cold_numbers=stats_context.get("cold_numbers", "None"),
            odd_even_ratio=stats_context.get("odd_even_ratio", "3:3"),
            consecutive_pairs=stats_context.get("consecutive_pairs", "None"),
            overdue_numbers=stats_context.get("overdue_numbers", "None"),
            bundle_intersection_context=bundle_inter_ctx,
            advanced_math_context=adv_math,
            temporal_bias_context=temporal_bias_context,
            environmental_anomalies_context=env_context,
        )

        messages = [
            {"role": "system", "content": PRIMARY_ANALYST_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        # Directive 13: 3-tier Graceful Degradation Pipeline
        try:
            raw_json = await self.call_qwen_json(messages)
            validated_response = AIGenerationResponse(**raw_json)
            validated_response.validate_against_game_rules()
        except Exception as primary_err:
            if not fallback_on_error:
                logger.error(f"Pydantic validation failed for Qwen board recommendation: {primary_err}")
                raise AIServiceError(f"Generated board failed schema validation: {primary_err}")

            logger.warning(
                f"Directive 13: Primary Qwen-Max generation failed after 3 retries ({primary_err}). "
                f"Degrading gracefully to Tier 2 Deterministic Statistical Generation..."
            )
            try:
                validated_response = self.generate_statistical_fallback(
                    game_type=game_type,
                    allocated_boards=allocated_boards,
                    stats_context=stats_context,
                    temporal_bias=temporal_bias,
                )
                validated_response.validate_against_game_rules()
            except Exception as stat_err:
                logger.error(
                    f"Directive 13: Tier 2 statistical fallback failed ({stat_err}). "
                    f"Degrading gracefully to Tier 3 secrets random generation..."
                )
                validated_response = self.generate_secrets_random_fallback(
                    game_type=game_type,
                    allocated_boards=allocated_boards,
                )
                validated_response.validate_against_game_rules()

        # Directive 18: Combinatorial Abbreviated Wheeling
        # If allocated_boards > 1 and candidate pool provided, wheel the pool to maximize coverage and EV
        main_count = rules.get("main_numbers_count", 6)
        if allocated_boards > 1 and validated_response.pool and len(validated_response.pool) >= main_count:
            try:
                from app.services.wheel_service import WheelService
                wheel_svc = WheelService()
                first_board = validated_response.boards[0] if validated_response.boards else None
                pb_val = first_board.bonus_or_powerball if first_board else None
                conf_val = first_board.confidence_score if first_board else 85.0
                is_fallback = "fallback" in (first_board.reasoning.lower() if first_board and first_board.reasoning else "")
                custom_reason = (
                    "Deterministic statistical fallback: Combinatorial abbreviated wheeling with EV optimization."
                    if is_fallback
                    else None
                )
                wheeled = wheel_svc.wheel_candidate_pool(
                    pool=validated_response.pool,
                    board_count=allocated_boards,
                    game_type=game_type,
                    bonus_or_powerball=pb_val,
                    base_confidence=conf_val,
                    custom_reasoning=custom_reason,
                )
                if wheeled:
                    validated_response.boards = wheeled
                    logger.info(
                        f"Directive 18: Successfully wheeled {len(validated_response.pool)} candidates "
                        f"into {len(wheeled)} boards for {game_type.value}."
                    )
            except Exception as wheel_err:
                logger.warning(f"Combinatorial wheeling encountered error, retaining original boards: {wheel_err}")

        # Directive 15: Run local Python Monte Carlo simulation (minimum 10,000 iterations)
        if historical_draws:
            from app.services.stats_service import StatsService
            stats_svc = StatsService()
            mc_results = stats_svc.run_monte_carlo_stress_test(
                boards=validated_response.boards,
                historical_draws=historical_draws,
                game_type=game_type,
                iterations=10000,
            )
            for idx, (b, mc) in enumerate(zip(validated_response.boards, mc_results)):
                logger.info(
                    f"Board #{idx + 1} Monte Carlo Stress Test: simulated hit rate = {mc.simulated_hit_rate * 100:.2f}% "
                    f"({mc.iterations:,} iterations)"
                )

        logger.info(
            f"Successfully generated and validated {len(validated_response.boards)} boards "
            f"for {game_type.value}."
        )
        return validated_response

    def generate_statistical_fallback(
        self,
        game_type: Union[GameType, BundleType, str],
        allocated_boards: int,
        stats_context: Dict[str, Any],
        temporal_bias: Optional[Dict[str, Any]] = None,
    ) -> AIGenerationResponse:
        """Directive 13: Tier 2 fallback - Deterministic statistical generation."""
        raw_key = game_type.value if hasattr(game_type, "value") else str(game_type)
        if raw_key in ("LOTTO_FAMILY", "POWERBALL_FAMILY"):
            rules = BUNDLE_RULES.get(BundleType(raw_key), {})
        else:
            rules = GAME_RULES.get(game_type, {})
        main_count = rules.get("main_numbers_count", 6)
        main_min = rules.get("main_number_min", 1)
        main_max = rules.get("main_number_max", 52)
        has_pb = rules.get("has_powerball", False)

        def _parse_nums(val: Any) -> List[int]:
            if isinstance(val, list):
                return [int(x) for x in val if isinstance(x, (int, str)) and str(x).isdigit()]
            elif isinstance(val, str) and val not in ("None", "None detected"):
                return [int(x.strip()) for x in val.split(",") if x.strip().isdigit()]
            return []

        hot = _parse_nums(stats_context.get("hot_numbers"))
        cold = _parse_nums(stats_context.get("cold_numbers"))
        overdue = _parse_nums(stats_context.get("overdue_numbers"))

        if temporal_bias and isinstance(temporal_bias, dict):
            boost = temporal_bias.get("boost_numbers") or []
            if boost:
                hot = list(dict.fromkeys(boost + hot))

        all_pool = list(range(main_min, main_max + 1))

        # Directive 18 & 20: Build balanced candidate pool with high-EV bias (>31)
        candidate_pool: List[int] = []
        for n in hot:
            if n not in candidate_pool and main_min <= n <= main_max:
                candidate_pool.append(n)
            if len(candidate_pool) >= 4:
                break
        for n in cold:
            if n not in candidate_pool and main_min <= n <= main_max:
                candidate_pool.append(n)
            if len(candidate_pool) >= 7:
                break
        for n in overdue:
            if n not in candidate_pool and main_min <= n <= main_max:
                candidate_pool.append(n)
            if len(candidate_pool) >= 9:
                break
        high_ev_cands = [n for n in range(max(32, main_min), main_max + 1) if n not in candidate_pool]
        for n in high_ev_cands:
            candidate_pool.append(n)
            if len(candidate_pool) >= 12:
                break
        candidate_pool.sort()

        boards: List[AIBoardRecommendation] = []

        if allocated_boards > 1 and len(candidate_pool) >= main_count:
            try:
                from app.services.wheel_service import WheelService
                wheel_svc = WheelService()
                pb_default = rules.get("powerball_min", 1) if has_pb else None
                boards = wheel_svc.wheel_candidate_pool(
                    pool=candidate_pool,
                    board_count=allocated_boards,
                    game_type=game_type,
                    bonus_or_powerball=pb_default,
                    base_confidence=70.0,
                    custom_reasoning="Statistical fallback: Combinatorial abbreviated wheeling with EV optimization.",
                )
            except Exception as wheel_err:
                logger.warning(f"Fallback wheeling failed, using sequential selection: {wheel_err}")
                boards = []

        if not boards:
            for b_idx in range(allocated_boards):
                chosen = set()

                # Take 2-3 hot numbers
                for n in hot[b_idx:]:
                    if len(chosen) < min(3, main_count - 2) and main_min <= n <= main_max:
                        chosen.add(n)

                # Take 1-2 cold numbers
                for n in cold[b_idx:]:
                    if len(chosen) < min(5, main_count - 1) and main_min <= n <= main_max:
                        chosen.add(n)

                # Take 1 overdue number
                for n in overdue[b_idx:]:
                    if len(chosen) < main_count and main_min <= n <= main_max:
                        chosen.add(n)

                # Fill remaining deterministically from pool
                offset = (b_idx * 7) % len(all_pool)
                cycler = all_pool[offset:] + all_pool[:offset]
                for n in cycler:
                    if len(chosen) >= main_count:
                        break
                    chosen.add(n)

                pb = None
                if has_pb:
                    pb_min = rules.get("powerball_min", 1)
                    pb_max = rules.get("powerball_max", 16)
                    pb = pb_min + (b_idx % (pb_max - pb_min + 1))

                boards.append(
                    AIBoardRecommendation(
                        numbers=sorted(list(chosen)),
                        bonus_or_powerball=pb,
                        confidence_score=70.0,
                        reasoning="Deterministic statistical fallback: balanced historical frequency and parity distribution.",
                    )
                )

        return AIGenerationResponse(
            game_type=game_type.value,
            boards=boards,
            pool=candidate_pool if candidate_pool else None,
            statistical_analysis_summary="Graceful degradation Tier 2: Deterministic statistical fallback with EV-optimized wheeling applied.",
        )

    def generate_secrets_random_fallback(
        self,
        game_type: Union[GameType, BundleType, str],
        allocated_boards: int,
    ) -> AIGenerationResponse:
        """Directive 13: Tier 3 fallback - Cryptographically secure random generation via secrets."""
        raw_key = game_type.value if hasattr(game_type, "value") else str(game_type)
        if raw_key in ("LOTTO_FAMILY", "POWERBALL_FAMILY"):
            rules = BUNDLE_RULES.get(BundleType(raw_key), {})
        else:
            rules = GAME_RULES.get(game_type, {})
        main_count = rules.get("main_numbers_count", 6)
        main_min = rules.get("main_number_min", 1)
        main_max = rules.get("main_number_max", 52)
        has_pb = rules.get("has_powerball", False)

        sr = secrets.SystemRandom()
        boards: List[AIBoardRecommendation] = []

        for _ in range(allocated_boards):
            chosen = sorted(sr.sample(range(main_min, main_max + 1), main_count))
            pb = None
            if has_pb:
                pb_min = rules.get("powerball_min", 1)
                pb_max = rules.get("powerball_max", 16)
                pb = sr.randint(pb_min, pb_max)

            boards.append(
                AIBoardRecommendation(
                    numbers=chosen,
                    bonus_or_powerball=pb,
                    confidence_score=50.0,
                    reasoning="Graceful degradation Tier 3: Cryptographically secure random generation via secrets module.",
                )
            )

        return AIGenerationResponse(
            game_type=game_type.value,
            boards=boards,
            statistical_analysis_summary="Graceful degradation Tier 3: Cryptographically random fallback applied.",
        )

    async def review_weekly_patterns(
        self,
        game_type: GameType,
        analysis_date: date,
        weekly_metrics: TemporalMetrics,
        monthly_metrics: TemporalMetrics,
    ) -> TemporalPatternReviewResponse:
        """Executes weekly pattern discovery comparing short-term variance against baseline."""
        logger.info(
            f"Invoking {self.analytics_model} weekly pattern review for {game_type.value} on {analysis_date}"
        )

        weekly_freq_str = ", ".join(
            f"{k}:{v}" for k, v in sorted(weekly_metrics.frequency_map.items(), key=lambda x: x[1], reverse=True)[:8]
        ) or "None"
        weekly_pairs_str = ", ".join(
            f"{k} (x{v})" for k, v in sorted(weekly_metrics.co_occurrence_matrix.items(), key=lambda x: x[1], reverse=True)[:5]
        ) or "None"

        monthly_freq_str = ", ".join(
            f"{k}:{v}" for k, v in sorted(monthly_metrics.frequency_map.items(), key=lambda x: x[1], reverse=True)[:10]
        ) or "None"
        monthly_pairs_str = ", ".join(
            f"{k} (x{v})" for k, v in sorted(monthly_metrics.co_occurrence_matrix.items(), key=lambda x: x[1], reverse=True)[:8]
        ) or "None"

        user_content = WEEKLY_PATTERN_REVIEW_USER_PROMPT.format(
            game_type=game_type.value,
            analysis_date=analysis_date.isoformat(),
            weekly_draws_count=weekly_metrics.sample_draws_count,
            weekly_sum_avg=weekly_metrics.sum_average,
            weekly_sum_std=weekly_metrics.sum_std_dev,
            weekly_parity=weekly_metrics.parity_ratio,
            weekly_top_freq=weekly_freq_str,
            weekly_top_pairs=weekly_pairs_str,
            monthly_draws_count=monthly_metrics.sample_draws_count,
            monthly_sum_avg=monthly_metrics.sum_average,
            monthly_sum_std=monthly_metrics.sum_std_dev,
            monthly_parity=monthly_metrics.parity_ratio,
            monthly_top_freq=monthly_freq_str,
            monthly_top_pairs=monthly_pairs_str,
        )

        messages = [
            {"role": "system", "content": WEEKLY_PATTERN_REVIEW_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        raw_json = await self.call_qwen_json(messages, temperature=0.5, model=self.analytics_model)

        try:
            validated_review = TemporalPatternReviewResponse(**raw_json)
        except Exception as val_err:
            logger.error(f"Weekly pattern review failed schema validation: {val_err}")
            raise AIServiceError(f"Pattern review failed schema validation: {val_err}")

        return validated_review

    async def review_monthly_deep_dive(
        self,
        game_type: GameType,
        analysis_date: date,
        weekly_records: List[TemporalAnalytics],
        monthly_metrics: TemporalMetrics,
    ) -> TemporalPatternReviewResponse:
        """Executes monthly macro deep-dive reviewing past multi-week summaries."""
        logger.info(
            f"Invoking {self.analytics_model} monthly deep dive for {game_type.value} on {analysis_date}"
        )

        lines = []
        for r in weekly_records:
            lines.append(
                f"- Week of {r.analysis_date} ({r.sample_draws_count} draws): "
                f"sum_avg={r.sum_average}, parity={r.parity_ratio}. "
                f"Insights: {r.ai_insights or 'None'}"
            )
        summaries_block = "\n".join(lines) if lines else "No previous weekly records available."

        monthly_pairs_str = ", ".join(
            f"{k} (x{v})" for k, v in sorted(monthly_metrics.co_occurrence_matrix.items(), key=lambda x: x[1], reverse=True)[:10]
        ) or "None"

        user_content = MONTHLY_DEEP_DIVE_USER_PROMPT.format(
            game_type=game_type.value,
            year_month=analysis_date.strftime("%Y-%m"),
            weekly_summaries_block=summaries_block,
            monthly_sum_avg=monthly_metrics.sum_average,
            monthly_sum_std=monthly_metrics.sum_std_dev,
            monthly_parity=monthly_metrics.parity_ratio,
            monthly_top_pairs=monthly_pairs_str,
        )

        messages = [
            {"role": "system", "content": MONTHLY_DEEP_DIVE_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        raw_json = await self.call_qwen_json(messages, temperature=0.5, model=self.analytics_model)

        try:
            validated_review = TemporalPatternReviewResponse(**raw_json)
        except Exception as val_err:
            logger.error(f"Monthly deep dive failed schema validation: {val_err}")
            raise AIServiceError(f"Monthly deep dive failed schema validation: {val_err}")

        return validated_review

    async def analyze_draw_performance(
        self,
        draw: Draw,
        boards: List[GeneratedBoard],
        results: List[BoardResult],
    ) -> PostDrawFeedbackResponse:
        """Executes the post-draw feedback loop analyzing deviations between predictions and outcomes."""
        logger.info(
            f"Initiating Post-Draw feedback loop for Draw #{draw.draw_number} ({draw.game_type})."
        )

        # Format evaluated boards summary for the reviewer prompt
        lines = []
        for b in boards:
            r = next((res for res in results if res.board_id == b.id), None)
            matched = r.matched_count if r else 0
            division = r.division if r else "None"
            prize = r.prize_amount if r else 0.0
            lines.append(
                f"- Board #{b.id}: numbers={b.numbers}, powerball/bonus={b.bonus_or_powerball}, "
                f"confidence={b.confidence_score}%, matched={matched}, division={division}, prize=R{prize}. "
                f"Reasoning='{b.ai_reasoning}'"
            )

        evaluated_summary = "\n".join(lines) if lines else "No boards evaluated for this draw."

        special_ball = draw.bonus_ball or draw.powerball or "None"

        user_content = POST_DRAW_FEEDBACK_USER_PROMPT.format(
            game_type=draw.game_type,
            draw_date=draw.draw_date.isoformat(),
            winning_numbers=str(draw.numbers),
            special_ball=str(special_ball),
            evaluated_boards=evaluated_summary,
        )

        messages = [
            {"role": "system", "content": POST_DRAW_FEEDBACK_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        raw_json = await self.call_qwen_json(messages, temperature=0.3)

        try:
            validated_feedback = PostDrawFeedbackResponse(**raw_json)
        except Exception as val_err:
            logger.error(f"PostDrawFeedback schema validation failed: {val_err}")
            raise AIServiceError(f"Feedback loop failed schema validation: {val_err}")

        logger.info(
            f"Feedback analysis complete for Draw #{draw.draw_number}: "
            f"accuracy={validated_feedback.accuracy_rate * 100:.1f}%"
        )
        return validated_feedback
