"""Unit tests for Notifier service.

Tests Telegram Bot and Discord Webhook alert formatting and dispatching.
"""
from decimal import Decimal
from unittest.mock import AsyncMock, patch
import httpx
import pytest
from app.services.notifier import Notifier


@pytest.fixture
def notifier():
    return Notifier(
        telegram_token="mock_token",
        telegram_chat_id="mock_chat_id",
        discord_webhook_url="https://discord.com/api/webhooks/mock",
    )


@pytest.fixture
def unconfigured_notifier():
    return Notifier(telegram_token=None, telegram_chat_id=None, discord_webhook_url=None)


@pytest.mark.asyncio
async def test_telegram_send_success(notifier):
    """Dispatches markdown text to Telegram API."""
    mock_resp = httpx.Response(status_code=200, request=httpx.Request("POST", "https://api.telegram.org"))
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
        success = await notifier.send_telegram("*Test Message*")
        assert success is True
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "sendMessage" in args[0]
        assert kwargs["json"]["chat_id"] == "mock_chat_id"
        assert kwargs["json"]["text"] == "*Test Message*"


@pytest.mark.asyncio
async def test_discord_send_success(notifier):
    """Dispatches payload to Discord webhook URL."""
    mock_resp = httpx.Response(status_code=204, request=httpx.Request("POST", "https://discord.com/mock"))
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
        success = await notifier.send_discord("Hello Discord")
        assert success is True
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert kwargs["json"]["content"] == "Hello Discord"


@pytest.mark.asyncio
async def test_unconfigured_notifier_fallback(unconfigured_notifier):
    """Gracefully falls back to local logging when tokens/webhooks are not set."""
    # Should not raise exception
    await unconfigured_notifier.notify_budget_exhaustion(
        year_month="2026-10",
        remaining_boards=0,
        total_budget="200.00",
    )

    await unconfigured_notifier.notify_high_matches(
        game_type="LOTTO",
        draw_number=2690,
        winning_boards=[{"board_id": 1, "matched_count": 5, "division": "Division 2", "prize": Decimal("85000.00")}],
        total_prize=Decimal("85000.00"),
    )

    await unconfigured_notifier.notify_draw_summary(
        game_type="LOTTO",
        draw_date="2026-10-21",
        total_boards=5,
        total_winnings=Decimal("85000.00"),
        roi_percentage=339900.0,
    )

    await unconfigured_notifier.notify_draw_completion(
        game_type="POWERBALL",
        draw_number=1766,
        draw_date="2026-10-23",
        winning_numbers=[1, 14, 22, 35, 41],
        bonus_or_pb=12,
        board_evaluations=[
            {
                "board_id": 10,
                "numbers": [16, 21, 33, 40, 48],
                "bonus_or_pb": 12,
                "matched_count": 0,
                "division": "Division 9",
                "prize": Decimal("15.00"),
            }
        ],
        total_winnings=Decimal("15.00"),
        total_cost=Decimal("10.00"),
        roi_percentage=50.0,
    )
