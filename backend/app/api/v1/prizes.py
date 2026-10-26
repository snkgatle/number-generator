"""Prize tier reference endpoint — static SA lottery payout mapping."""
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException
from app.schemas.enums import GAME_RULES, GameType
from app.services.prize_service import (
    LOTTO_PRIZE_TIERS,
    LOTTO_PLUS_PRIZE_TIERS,
    POWERBALL_PRIZE_TIERS,
)

router = APIRouter(prefix="/prizes", tags=["Prizes"])

TIER_MAP: Dict[str, List[Dict[str, Any]]] = {
    "LOTTO": LOTTO_PRIZE_TIERS,
    "LOTTO_PLUS_1": LOTTO_PLUS_PRIZE_TIERS,
    "LOTTO_PLUS_2": LOTTO_PLUS_PRIZE_TIERS,
    "POWERBALL": POWERBALL_PRIZE_TIERS,
    "POWERBALL_PLUS": POWERBALL_PRIZE_TIERS,
}


@router.get("/tiers/{game_type}")
async def get_prize_tiers(game_type: str):
    """Return the full static prize tier mapping for the specified game."""
    # Normalize bundle names → use first member's tiers
    key = game_type
    if key == "LOTTO_FAMILY":
        key = "LOTTO"
    elif key == "POWERBALL_FAMILY":
        key = "POWERBALL"

    if key not in TIER_MAP:
        raise HTTPException(status_code=404, detail=f"Unknown game type: {game_type}")

    return {
        "game_type": key,
        "matrix": _get_matrix(key),
        "tiers": TIER_MAP[key],
    }


def _get_matrix(key: str) -> Dict[str, Any]:
    rules = GAME_RULES.get(key, {})
    return {
        "main_numbers_count": rules.get("main_numbers_count"),
        "main_number_min": rules.get("main_number_min"),
        "main_number_max": rules.get("main_number_max"),
        "has_powerball": rules.get("has_powerball", False),
    }
