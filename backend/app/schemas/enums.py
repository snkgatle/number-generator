"""Enumerations for lottery games, game bundles, and board statuses."""
from datetime import date, timedelta
from enum import Enum
from typing import Dict, List, Optional, Union


class GameType(str, Enum):
    """Supported South African lottery sub-draw games."""
    LOTTO = "LOTTO"
    LOTTO_PLUS_1 = "LOTTO_PLUS_1"
    LOTTO_PLUS_2 = "LOTTO_PLUS_2"
    POWERBALL = "POWERBALL"
    POWERBALL_PLUS = "POWERBALL_PLUS"


class BundleType(str, Enum):
    """Playable lottery bundles grouping sub-draws (Directive 21).

    One generated board applies to all sub-draws within the bundle.
    """
    LOTTO_FAMILY = "LOTTO_FAMILY"
    POWERBALL_FAMILY = "POWERBALL_FAMILY"


class BoardStatus(str, Enum):
    """Lifecycle statuses for generated boards."""
    PENDING = "PENDING"
    EVALUATED = "EVALUATED"
    WON = "WON"
    LOST = "LOST"
    VOID = "VOID"


# Mapping from bundles to member sub-draws
BUNDLE_GAMES: Dict[BundleType, List[GameType]] = {
    BundleType.LOTTO_FAMILY: [GameType.LOTTO, GameType.LOTTO_PLUS_1, GameType.LOTTO_PLUS_2],
    BundleType.POWERBALL_FAMILY: [GameType.POWERBALL, GameType.POWERBALL_PLUS],
}

# Reverse mapping from sub-draw to parent bundle
GAME_TO_BUNDLE: Dict[GameType, BundleType] = {
    GameType.LOTTO: BundleType.LOTTO_FAMILY,
    GameType.LOTTO_PLUS_1: BundleType.LOTTO_FAMILY,
    GameType.LOTTO_PLUS_2: BundleType.LOTTO_FAMILY,
    GameType.POWERBALL: BundleType.POWERBALL_FAMILY,
    GameType.POWERBALL_PLUS: BundleType.POWERBALL_FAMILY,
}


# Game matrix specifications (used in validation and prompt engineering)
GAME_RULES = {
    GameType.LOTTO: {
        "main_numbers_count": 6,
        "main_number_min": 1,
        "main_number_max": 52,
        "has_bonus": True,
        "bonus_min": 1,
        "bonus_max": 52,
        "has_powerball": False,
    },
    GameType.LOTTO_PLUS_1: {
        "main_numbers_count": 6,
        "main_number_min": 1,
        "main_number_max": 52,
        "has_bonus": True,
        "bonus_min": 1,
        "bonus_max": 52,
        "has_powerball": False,
    },
    GameType.LOTTO_PLUS_2: {
        "main_numbers_count": 6,
        "main_number_min": 1,
        "main_number_max": 52,
        "has_bonus": True,
        "bonus_min": 1,
        "bonus_max": 52,
        "has_powerball": False,
    },
    GameType.POWERBALL: {
        "main_numbers_count": 5,
        "main_number_min": 1,
        "main_number_max": 50,
        "has_bonus": False,
        "has_powerball": True,
        "powerball_min": 1,
        "powerball_max": 16,
    },
    GameType.POWERBALL_PLUS: {
        "main_numbers_count": 5,
        "main_number_min": 1,
        "main_number_max": 50,
        "has_bonus": False,
        "has_powerball": True,
        "powerball_min": 1,
        "powerball_max": 16,
    },
}

# Bundle specifications (matrix rules and true bundled cost)
BUNDLE_RULES = {
    BundleType.LOTTO_FAMILY: {
        "bundle_name": "LOTTO_FAMILY",
        "display_name": "Lotto Bundle (Lotto + Plus 1 + Plus 2)",
        "main_numbers_count": 6,
        "main_number_min": 1,
        "main_number_max": 52,
        "has_bonus": True,
        "has_powerball": False,
        "total_cost": 10.00,
    },
    BundleType.POWERBALL_FAMILY: {
        "bundle_name": "POWERBALL_FAMILY",
        "display_name": "PowerBall Bundle (PowerBall + PowerBall Plus)",
        "main_numbers_count": 5,
        "main_number_min": 1,
        "main_number_max": 50,
        "has_bonus": False,
        "has_powerball": True,
        "powerball_min": 1,
        "powerball_max": 16,
        "total_cost": 10.00,
    },
}

# Standard draw schedule mapping by weekday (0=Monday, 1=Tuesday, ..., 6=Sunday)
GAME_DRAW_DAYS = {
    GameType.POWERBALL: [1, 4],          # Tuesday, Friday
    GameType.POWERBALL_PLUS: [1, 4],     # Tuesday, Friday
    GameType.LOTTO: [2, 5],              # Wednesday, Saturday
    GameType.LOTTO_PLUS_1: [2, 5],       # Wednesday, Saturday
    GameType.LOTTO_PLUS_2: [2, 5],       # Wednesday, Saturday
}

BUNDLE_DRAW_DAYS = {
    BundleType.POWERBALL_FAMILY: [1, 4],  # Tuesday, Friday
    BundleType.LOTTO_FAMILY: [2, 5],      # Wednesday, Saturday
}


def game_key(game_or_bundle: Union[GameType, BundleType, str]) -> str:
    """Normalizes a GameType, BundleType, or raw string to its canonical string key."""
    return game_or_bundle.value if hasattr(game_or_bundle, "value") else str(game_or_bundle)


def resolve_rules(game_or_bundle: Union[GameType, BundleType, str]) -> Dict:
    """Resolves the matrix rules for any game or bundle identifier (enum or raw string).

    Returns BUNDLE_RULES for bundle keys, GAME_RULES for sub-game keys,
    and an empty dict for unrecognized values.
    """
    key = game_key(game_or_bundle)
    if key in ("LOTTO_FAMILY", "POWERBALL_FAMILY"):
        return BUNDLE_RULES.get(BundleType(key), {})
    try:
        return GAME_RULES.get(GameType(key), {})
    except ValueError:
        return {}


def get_next_draw_date(game_or_bundle: Union[GameType, BundleType, str], ref_date: Optional[date] = None) -> date:
    """Calculates upcoming scheduled draw date for a given game or bundle."""
    base = ref_date or date.today()
    val = game_or_bundle.value if hasattr(game_or_bundle, "value") else str(game_or_bundle)

    if val in ("POWERBALL_FAMILY", "POWERBALL", "POWERBALL_PLUS"):
        draw_days = [1, 4]
    else:
        draw_days = [2, 5]

    for offset in range(7):
        candidate = base + timedelta(days=offset)
        if candidate.weekday() in draw_days:
            return candidate
    return base


def get_next_bundle_draw_date(bundle_type: BundleType, ref_date: Optional[date] = None) -> date:
    """Calculates upcoming scheduled draw date for a given game bundle."""
    return get_next_draw_date(bundle_type, ref_date)
