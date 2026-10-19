"""Pydantic schemas for lottery draws."""
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.schemas.enums import GameType, GAME_RULES


class DrawBase(BaseModel):
    """Base schema for lottery draws."""
    draw_number: int = Field(..., gt=0, description="Official lottery draw number")
    game_type: GameType = Field(..., description="Type of lottery game")
    draw_date: date = Field(..., description="Date of the official draw")
    numbers: List[int] = Field(..., description="Sorted list of winning numbers drawn")
    bonus_ball: Optional[int] = Field(None, ge=1, le=52, description="Bonus ball number if applicable")
    powerball: Optional[int] = Field(None, ge=1, le=20, description="Powerball number if applicable")
    raw_data: Optional[Dict[str, Any]] = Field(default=None, description="Raw scraped payload/metadata")

    @field_validator("numbers")
    @classmethod
    def validate_and_sort_numbers(cls, v: List[int]) -> List[int]:
        if not v:
            raise ValueError("Numbers list cannot be empty")
        if len(v) != len(set(v)):
            raise ValueError("Winning numbers must be unique")
        return sorted(v)


class DrawCreate(DrawBase):
    """Schema for inserting a newly scraped or imported draw."""

    @field_validator("numbers")
    @classmethod
    def validate_game_matrix(cls, numbers: List[int], info) -> List[int]:
        game_type = info.data.get("game_type")
        if game_type and game_type in GAME_RULES:
            rules = GAME_RULES[game_type]
            expected_count = rules["main_numbers_count"]
            if len(numbers) != expected_count:
                raise ValueError(
                    f"{game_type} requires exactly {expected_count} numbers, got {len(numbers)}"
                )
            for n in numbers:
                if not (rules["main_number_min"] <= n <= rules["main_number_max"]):
                    raise ValueError(
                        f"Number {n} out of bounds for {game_type} "
                        f"({rules['main_number_min']}-{rules['main_number_max']})"
                    )
        return numbers


class DrawUpdate(BaseModel):
    """Schema for updating draw details."""
    numbers: Optional[List[int]] = None
    bonus_ball: Optional[int] = None
    powerball: Optional[int] = None
    raw_data: Optional[Dict[str, Any]] = None


class DrawResponse(DrawBase):
    """Schema for returning draw data from API endpoints."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class DrawListResponse(BaseModel):
    """Paginated or listed response of draws."""
    total: int
    items: List[DrawResponse]


class ScrapeRequest(BaseModel):
    """Payload to trigger manual or automated scraping."""
    game_types: Optional[List[GameType]] = Field(
        None,
        description="List of game types to scrape. If omitted, all games are scraped.",
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Number of recent draws to fetch per game (up to 50 draws as per roadmap).",
    )


class ScrapeGameResult(BaseModel):
    """Summary of scraping execution for a single game type."""
    game_type: GameType
    draws_found: int
    draws_inserted: int
    latest_draw_number: Optional[int] = None
    status: str = "success"
    error: Optional[str] = None


class ScrapeResponse(BaseModel):
    """Aggregated response returned by manual or scheduled scrape runs."""
    status: str
    total_found: int
    total_inserted: int
    details: List[ScrapeGameResult]
    message: str
