"""Enumerations for lottery games and board statuses."""
from enum import Enum


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
