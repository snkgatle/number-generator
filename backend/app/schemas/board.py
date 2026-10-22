"""Pydantic schemas for generated boards, evaluation results, and AI JSON contracts."""
import re
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.schemas.enums import (
    BoardStatus,
    BundleType,
    GameType,
    GAME_RULES,
    BUNDLE_RULES,
    GAME_TO_BUNDLE,
)


class GeneratedBoardBase(BaseModel):
    """Base schema for an AI-generated lottery board."""
    bundle_name: str = Field(default="LOTTO_FAMILY", description="Lottery bundle name (Directive 21)")
    game_type: Optional[str] = Field(None, description="Alias matching bundle_name for backwards compatibility")
    target_draw_date: date = Field(..., description="Target draw date for this ticket")
    numbers: List[int] = Field(..., description="Sorted list of numbers")
    bonus_or_powerball: Optional[int] = Field(None, description="Powerball or bonus number")
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Confidence percentage (0.0 to 100.0) assigned by Qwen-Max",
    )
    ai_reasoning: Optional[str] = Field(None, description="Analytical reasoning provided by AI")
    status: BoardStatus = Field(default=BoardStatus.PENDING, description="Board lifecycle status")
    cost: Decimal = Field(default=Decimal("10.00"), ge=0, description="Cost of the bundled board in ZAR (R10.00)")

    @field_validator("numbers")
    @classmethod
    def validate_and_sort_numbers(cls, v: List[int]) -> List[int]:
        if not v:
            raise ValueError("Numbers cannot be empty")
        if len(v) != len(set(v)):
            raise ValueError("Board numbers must be unique")
        return sorted(v)


class GeneratedBoardCreate(GeneratedBoardBase):
    """Payload to create a generated board."""
    bundle_id: Optional[int] = None
    budget_id: Optional[int] = None
    draw_id: Optional[int] = None


class GeneratedBoardResponse(GeneratedBoardBase):
    """Schema returned for generated board entities."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    bundle_id: Optional[int] = None
    budget_id: Optional[int] = None
    draw_id: Optional[int] = None
    created_at: datetime


class BoardResultBase(BaseModel):
    """Base schema for board match results."""
    board_id: int
    draw_id: int
    game_type: str = Field(default="", description="Specific sub-draw game type (e.g., LOTTO, LOTTO_PLUS_1)")
    matched_numbers: List[int] = Field(default_factory=list)
    matched_count: int = Field(default=0, ge=0)
    matched_bonus: bool = Field(default=False)
    division: Optional[str] = None
    prize_amount: Decimal = Field(default=Decimal("0.00"), ge=0)


class BoardResultCreate(BoardResultBase):
    """Schema for recording post-draw evaluation outcomes."""
    pass


class BoardResultResponse(BoardResultBase):
    """Schema returned for board result queries."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    evaluated_at: datetime


class BoardWithResultResponse(GeneratedBoardResponse):
    """Detailed response of a board with its post-draw evaluation across sub-draws."""
    results: List[BoardResultResponse] = Field(default_factory=list)
    result: Optional[BoardResultResponse] = None
    total_prize: Decimal = Field(default=Decimal("0.00"), description="Sum of prizes across all sub-draws (Directive 24)")


# ==============================================================================
# Strict JSON Enforcement Schemas for Qwen-Max Integration (Directive 2)
# ==============================================================================

class AIBoardRecommendation(BaseModel):
    """Single board recommendation structure output by Qwen-Max."""
    numbers: List[int] = Field(..., description="Main numbers selected based on statistics")
    bonus_or_powerball: Optional[int] = Field(
        None,
        description="Powerball number (1-16) if Powerball bundle, otherwise null",
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Confidence percentage (0.0 - 100.0)",
    )
    reasoning: str = Field(
        ...,
        min_length=10,
        description="Statistical rationale (hot/cold balance, parity ratio, etc.)",
    )

    @field_validator("numbers", mode="before")
    @classmethod
    def validate_numbers_sorted_and_unique(cls, v) -> List[int]:
        if isinstance(v, int):
            v = [v]
        elif isinstance(v, str):
            nums = [int(n) for n in re.findall(r"\d+", v)]
            v = nums
        elif isinstance(v, (list, tuple)):
            v = [int(n) for n in v]
        else:
            raise ValueError("Numbers must be a list of integers")

        if not v:
            raise ValueError("Numbers cannot be empty")
        if len(v) != len(set(v)):
            raise ValueError("Numbers must be strictly unique")
        return sorted(v)


class AIGenerationResponse(BaseModel):
    """Root JSON structure enforced on Qwen-Max response."""
    game_type: Union[GameType, BundleType, str] = Field(..., description="Validated bundle or game type")
    boards: List[AIBoardRecommendation] = Field(
        ...,
        min_length=1,
        description="List of recommended boards",
    )
    statistical_analysis_summary: str = Field(
        ...,
        description="High-level statistical summary across the recent draw window",
    )
    pool: Optional[List[int]] = Field(
        default=None,
        description="Directive 18: High-confidence candidate pool (10-14 numbers) for combinatorial wheeling",
    )

    def validate_against_game_rules(self) -> None:
        """Validates all generated boards against official game or bundle matrix rules."""
        raw_key = self.game_type.value if hasattr(self.game_type, "value") else str(self.game_type)
        if raw_key in ("LOTTO_FAMILY", "POWERBALL_FAMILY"):
            rules = BUNDLE_RULES.get(BundleType(raw_key), {})
        else:
            rules = GAME_RULES.get(GameType(raw_key), {})

        if not rules:
            return

        expected_count = rules["main_numbers_count"]
        for idx, board in enumerate(self.boards, start=1):
            if len(board.numbers) != expected_count:
                raise ValueError(
                    f"Board #{idx} has {len(board.numbers)} numbers, "
                    f"expected {expected_count} for {self.game_type}"
                )
            for num in board.numbers:
                if not (rules["main_number_min"] <= num <= rules["main_number_max"]):
                    raise ValueError(
                        f"Board #{idx} number {num} out of bounds "
                        f"({rules['main_number_min']}-{rules['main_number_max']})"
                    )

            if rules.get("has_powerball"):
                if board.bonus_or_powerball is None:
                    raise ValueError(f"Board #{idx} missing powerball for {self.game_type}")
                pb = board.bonus_or_powerball
                if not (rules["powerball_min"] <= pb <= rules["powerball_max"]):
                    raise ValueError(
                        f"Board #{idx} powerball {pb} out of bounds "
                        f"({rules['powerball_min']}-{rules['powerball_max']})"
                    )


class GenerationRequest(BaseModel):
    """Payload to request board generation for an upcoming draw."""
    bundle_name: Optional[Union[BundleType, str]] = Field(
        None,
        description="Bundle identifier (LOTTO_FAMILY or POWERBALL_FAMILY)",
    )
    game_type: Optional[Union[GameType, BundleType, str]] = Field(
        None,
        description="Lottery game type or bundle name to generate",
    )
    target_draw_date: Optional[date] = Field(None, description="Optional target draw date (defaults to next draw)")
    allocated_boards: Optional[int] = Field(
        default=1,
        ge=1,
        le=10,
        description="Number of boards requested (subject to circuit breaker and budget allocation rules)",
    )

    def resolved_bundle(self) -> BundleType:
        """Resolves target BundleType from bundle_name or game_type."""
        target = self.bundle_name or self.game_type or BundleType.LOTTO_FAMILY
        target_str = target.value if hasattr(target, "value") else str(target)

        if target_str in ("LOTTO_FAMILY", "POWERBALL_FAMILY"):
            return BundleType(target_str)
        try:
            gt = GameType(target_str)
            return GAME_TO_BUNDLE.get(gt, BundleType.LOTTO_FAMILY)
        except ValueError:
            return BundleType.LOTTO_FAMILY


class PreDrawPipelineRequest(BaseModel):
    """Payload to trigger pre-draw pipeline."""
    bundles: Optional[List[Union[BundleType, str]]] = Field(None, description="Bundle families to run generation for")
    game_types: Optional[List[Union[GameType, BundleType, str]]] = Field(None, description="Legacy game types or bundles")
    target_date: Optional[date] = Field(None, description="Optional target draw date")


class PostDrawFeedbackResponse(BaseModel):
    """Schema returned by Qwen-Max analyzing performance deviations and recalibrations."""
    game_type: Union[GameType, BundleType, str]
    draw_date: str
    accuracy_rate: float = Field(..., ge=0.0, le=1.0, description="Proportion of predicted numbers that aligned")
    divergence_analysis: str = Field(..., description="In-depth post-mortem of statistical deviations")
    calibration_recommendations: List[str] = Field(
        default_factory=list,
        description="Actionable adjustments for future board generation prompts",
    )
