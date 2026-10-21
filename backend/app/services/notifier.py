"""Notification Service for Telegram and Discord webhooks.

Directive: Alerts for budget exhaustion and high-match lottery outcomes.
"""
from decimal import Decimal
from typing import Any, Dict, List, Optional
import httpx
from loguru import logger

from app.core.config import settings


class Notifier:
    """Dispatches webhook alerts to Telegram and Discord with graceful fallback logging."""

    def __init__(
        self,
        telegram_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
        discord_webhook_url: Optional[str] = None,
    ):
        self.telegram_token = telegram_token or settings.TELEGRAM_BOT_TOKEN
        self.telegram_chat_id = telegram_chat_id or settings.TELEGRAM_CHAT_ID
        self.discord_webhook = discord_webhook_url or settings.DISCORD_WEBHOOK_URL

    async def send_telegram(self, text: str) -> bool:
        """Sends a markdown message via Telegram Bot API."""
        if not self.telegram_token or not self.telegram_chat_id:
            return False

        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {
            "chat_id": self.telegram_chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    logger.debug("Telegram alert dispatched successfully.")
                    return True
                else:
                    logger.warning(f"Telegram API responded with [{res.status_code}]: {res.text}")
                    return False
        except Exception as exc:
            logger.error(f"Failed to deliver Telegram notification: {exc}")
            return False

    async def send_discord(self, text: str) -> bool:
        """Sends a message payload to Discord Webhook URL."""
        if not self.discord_webhook:
            return False

        payload = {"content": text}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(self.discord_webhook, json=payload)
                if res.status_code in (200, 204):
                    logger.debug("Discord webhook alert dispatched successfully.")
                    return True
                else:
                    logger.warning(f"Discord Webhook responded with [{res.status_code}]: {res.text}")
                    return False
        except Exception as exc:
            logger.error(f"Failed to deliver Discord notification: {exc}")
            return False

    async def broadcast(self, title: str, message: str) -> None:
        """Broadcasts to configured channels or logs locally if unconfigured."""
        formatted_text = f"🚨 *{title}*\n\n{message}"

        tg_sent = await self.send_telegram(formatted_text)
        dc_sent = await self.send_discord(formatted_text)

        if not tg_sent and not dc_sent:
            logger.info(f"Local Alert Broadcast (No webhook configured): [{title}] {message}")

    async def notify_budget_exhaustion(
        self, year_month: str, remaining_boards: int, total_budget: str
    ) -> None:
        """Directive 3 Circuit Breaker alert: Dispatches when monthly budget is exhausted."""
        title = "CIRCUIT BREAKER: Monthly Budget Exhausted"
        msg = (
            f"⚠️ Board generation has halted for cycle *{year_month}*.\n"
            f"- Remaining Boards: `{remaining_boards}`\n"
            f"- Total Budget: `R{total_budget}`\n"
            f"All subsequent board generation is blocked until rollover on the 25th."
        )
        await self.broadcast(title, msg)

    async def notify_high_matches(
        self,
        game_type: str,
        draw_number: int,
        winning_boards: List[Dict[str, Any]],
        total_prize: Decimal,
    ) -> None:
        """Alerts the user when high-ranking prize matches are scored."""
        title = f"🎉 WINNING BOARDS: {game_type} Draw #{draw_number}"
        lines = [f"Total Prize Yield: *R{total_prize:,.2f}*\n"]
        for b in winning_boards:
            lines.append(
                f"• Board #{b.get('board_id')}: Matched `{b.get('matched_count')}` numbers "
                f"({b.get('division')}) -> *R{b.get('prize', 0):,.2f}*"
            )
        msg = "\n".join(lines)
        await self.broadcast(title, msg)

    async def notify_draw_summary(
        self,
        game_type: str,
        draw_date: str,
        total_boards: int,
        total_winnings: Decimal,
        roi_percentage: float,
    ) -> None:
        """Dispatches post-draw financial summary."""
        title = f"📊 Post-Draw Evaluation: {game_type} ({draw_date})"
        msg = (
            f"- Total Boards Evaluated: `{total_boards}`\n"
            f"- Total Winnings: *R{total_winnings:,.2f}*\n"
            f"- Net Draw ROI: *{roi_percentage:+.2f}%*"
        )
        await self.broadcast(title, msg)
