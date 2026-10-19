"""Unit tests for Pydantic validation schemas and strict Qwen AI contracts."""
from datetime import date
from decimal import Decimal
import pytest
from pydantic import ValidationError

from app.schemas.draw import DrawCreate
from app.schemas.budget import MonthlyBudgetBase
from app.schemas.board import (
    GeneratedBoardCreate,
    AIBoardRecommendation,
    AIGenerationResponse,
)
from app.schemas.enums import GameType


def test_draw_create_lotto_validation():
    """Verify LOTTO schema validation: requires 6 unique numbers between 1-52."""
    valid_data = {
        "draw_number": 2040,
        "game_type": GameType.LOTTO,
        "draw_date": date(2026, 10, 14),
        "numbers": [42, 12, 5, 23, 19, 51],  # Unsorted
        "bonus_ball": 17,
    }
    draw = DrawCreate(**valid_data)
    # Ensure automatically sorted
    assert draw.numbers == [5, 12, 19, 23, 42, 51]

    # Test failure: only 5 numbers for LOTTO
    with pytest.raises(ValidationError) as exc:
        DrawCreate(**{**valid_data, "numbers": [1, 2, 3, 4, 5]})
    assert "requires exactly 6 numbers" in str(exc.value)

    # Test failure: out of bounds number (> 52)
    with pytest.raises(ValidationError) as exc:
        DrawCreate(**{**valid_data, "numbers": [1, 2, 3, 4, 5, 53]})
    assert "out of bounds" in str(exc.value)

    # Test failure: duplicate numbers
    with pytest.raises(ValidationError) as exc:
        DrawCreate(**{**valid_data, "numbers": [5, 5, 12, 19, 23, 42]})
    assert "must be unique" in str(exc.value)


def test_draw_create_powerball_validation():
    """Verify POWERBALL schema validation: requires 5 unique numbers between 1-50."""
    valid_pb = {
        "draw_number": 1500,
        "game_type": GameType.POWERBALL,
        "draw_date": date(2026, 10, 16),
        "numbers": [10, 20, 30, 40, 50],
        "powerball": 15,
    }
    draw = DrawCreate(**valid_pb)
    assert draw.numbers == [10, 20, 30, 40, 50]
    assert draw.powerball == 15

    # Test failure: 6 numbers for POWERBALL
    with pytest.raises(ValidationError) as exc:
        DrawCreate(**{**valid_pb, "numbers": [10, 20, 30, 40, 49, 50]})
    assert "requires exactly 5 numbers" in str(exc.value)


def test_budget_schema_year_month_regex():
    """Verify YYYY-MM formatting for monthly budgets."""
    valid = MonthlyBudgetBase(year_month="2026-10", total_budget=Decimal("200.00"))
    assert valid.year_month == "2026-10"

    with pytest.raises(ValidationError):
        MonthlyBudgetBase(year_month="2026-13")  # Invalid month

    with pytest.raises(ValidationError):
        MonthlyBudgetBase(year_month="October-2026")


def test_ai_structured_response_validation():
    """Directive 2: Strict JSON enforcement for Qwen-Max response payloads."""
    ai_raw_json = {
        "game_type": "POWERBALL",
        "boards": [
            {
                "numbers": [7, 14, 21, 35, 42],
                "bonus_or_powerball": 8,
                "confidence_score": 86.5,
                "reasoning": "High concentration around recent 3:2 odd/even ratio.",
            }
        ],
        "statistical_analysis_summary": "Evaluated last 50 draws; hot numbers dominated middle quadrant.",
    }

    parsed = AIGenerationResponse(**ai_raw_json)
    assert parsed.game_type == GameType.POWERBALL
    assert len(parsed.boards) == 1
    assert parsed.boards[0].confidence_score == 86.5

    # Verify game matrix rule check
    parsed.validate_against_game_rules()

    # Invalidate: Powerball out of bounds (> 20)
    invalid_pb = {
        **ai_raw_json,
        "boards": [
            {
                "numbers": [7, 14, 21, 35, 42],
                "bonus_or_powerball": 25,  # Powerball max is 20!
                "confidence_score": 80.0,
                "reasoning": "Test invalid powerball",
            }
        ],
    }
    with pytest.raises(ValueError) as exc:
        AIGenerationResponse(**invalid_pb).validate_against_game_rules()
    assert "powerball 25 out of bounds" in str(exc.value)
