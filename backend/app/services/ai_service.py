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
from typing import Any, Dict, List, Optional
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
from app.models.board import BoardResult, GeneratedBoard
from app.models.draw import Draw
from app.schemas.board import (
    AIGenerationResponse,
    PostDrawFeedbackResponse,
)
from app.schemas.enums import GameType
from app.services.prompts import (
    POST_DRAW_FEEDBACK_SYSTEM_PROMPT,
    POST_DRAW_FEEDBACK_USER_PROMPT,
    PRIMARY_ANALYST_SYSTEM_PROMPT,
    PRIMARY_GENERATION_USER_PROMPT,
)


class AIServiceError(Exception):
    """Raised when DashScope interaction or JSON parsing fails."""
    pass


class AIService:
    """Orchestrates structured probabilistic analysis and generation via Qwen-Max."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or settings.DASHSCOPE_API_KEY
        self.base_url = (base_url or settings.DASHSCOPE_BASE_URL).rstrip("/")
        self.model = settings.QWEN_MODEL or Generation.Models.qwen_max

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
        self, messages: List[Dict[str, str]], temperature: float = 0.7
    ) -> Dict[str, Any]:
        """Queries Qwen-Max expecting a strictly structured JSON response."""
        if not self.api_key:
            raise AIServiceError(
                "DashScope / Qwen API key is not configured. Set DASHSCOPE_API_KEY in .env."
            )

        logger.debug(f"Dispatching structured query to Qwen ({self.model}) at {self.base_url}...")

        # If using OpenAI-compatible mode endpoint (e.g., https://maas.qwencloudapi.com/compatible-mode/v1)
        if "compatible-mode" in self.base_url or "chat/completions" in self.base_url or "qwencloudapi" in self.base_url:
            import httpx

            url = f"{self.base_url}/chat/completions" if not self.base_url.endswith("/chat/completions") else self.base_url
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": self.model,
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
                    model=self.model,
                    messages=messages,
                    result_format="message",
                    temperature=temperature,
                    api_key=self.api_key,
                )

            response = await asyncio.to_thread(_blocking_call)

            if response.status_code != HTTPStatus.OK:
                err_code = getattr(response, "code", "UNKNOWN_ERROR")
                err_msg = getattr(response, "message", "No error message provided")
                logger.error(f"DashScope Qwen-Max error [{response.status_code}]: {err_code} - {err_msg}")
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
        game_type: GameType,
        target_draw_date: date,
        allocated_boards: int,
        stats_context: Dict[str, str],
    ) -> AIGenerationResponse:
        """Prompts Qwen-Max using isolated templates and validates output with Pydantic."""
        logger.info(
            f"Invoking Qwen-Max generation for {game_type.value} on {target_draw_date} "
            f"({allocated_boards} boards requested)"
        )

        from app.schemas.enums import GAME_RULES
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

        user_content = PRIMARY_GENERATION_USER_PROMPT.format(
            game_type=game_type.value,
            target_draw_date=target_draw_date.isoformat(),
            allocated_boards=allocated_boards,
            game_matrix_rules=rules_summary,
            hot_numbers=stats_context.get("hot_numbers", "None"),
            cold_numbers=stats_context.get("cold_numbers", "None"),
            odd_even_ratio=stats_context.get("odd_even_ratio", "3:3"),
            consecutive_pairs=stats_context.get("consecutive_pairs", "None"),
            overdue_numbers=stats_context.get("overdue_numbers", "None"),
        )

        messages = [
            {"role": "system", "content": PRIMARY_ANALYST_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        raw_json = await self.call_qwen_json(messages)

        # Directive 2: Strict JSON enforcement with Pydantic
        try:
            validated_response = AIGenerationResponse(**raw_json)
            validated_response.validate_against_game_rules()
        except Exception as validation_err:
            logger.error(f"Pydantic validation failed for Qwen board recommendation: {validation_err}")
            raise AIServiceError(f"Generated board failed schema validation: {validation_err}")

        logger.info(
            f"Successfully generated and validated {len(validated_response.boards)} boards "
            f"for {game_type.value}."
        )
        return validated_response

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
