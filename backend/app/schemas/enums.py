from datetime import date, timedelta
from enum import Enum
from typing import Optional


class GameType(str, Enum):
    """Supported South African lottery games."""
    LOTTO = "LOTTO"
    LOTTO_PLUS_1 = "LOTTO_PLUS_1"
    LOTTO_PLUS_2 = "LOTTO_PLUS_2"
    POWERBALL = "POWERBALL"
    POWERBALL_PLUS = "POWERBALL_PLUS"


class BoardStatus(str, Enum):
    """Lifecycle statuses for generated boards."""
    PENDING = "PENDING"
    EVALUATED = "EVALUATED"
    WON = "WON"
    LOST = "LOST"
    VOID = "VOID"


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

# Standard draw schedule mapping by weekday (0=Monday, 1=Tuesday, ..., 6=Sunday)
GAME_DRAW_DAYS = {
    GameType.POWERBALL: [1, 4],          # Tuesday, Friday
    GameType.POWERBALL_PLUS: [1, 4],     # Tuesday, Friday
    GameType.LOTTO: [2, 5],              # Wednesday, Saturday
    GameType.LOTTO_PLUS_1: [2, 5],       # Wednesday, Saturday
    GameType.LOTTO_PLUS_2: [2, 5],       # Wednesday, Saturday
}


def get_next_draw_date(game_type: GameType, ref_date: Optional[date] = None) -> date:
    """Calculates the upcoming scheduled draw date for a given lottery game."""
    base = ref_date or date.today()
    draw_days = GAME_DRAW_DAYS.get(game_type, [1, 2, 4, 5])

    for offset in range(7):
        candidate = base + timedelta(days=offset)
        if candidate.weekday() in draw_days:
            return candidate
    return base

