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

    async def send_telegram_otp(self, otp_code: str) -> bool:
        """Directive 25: Sends a single-use 6-digit login OTP code to the authorized Telegram Chat."""
        text = (
            f"🔐 *LottoMind Login Verification*\n\n"
            f"Your one-time login code is:\n\n"
            f"👉 `{otp_code}` 👈\n\n"
            f"⏱️ This code expires in 10 minutes. If you did not request this, please disregard."
        )
        return await self.send_telegram(text)

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

    async def notify_draw_completion(
        self,
        game_type: str,
        draw_number: int,
        draw_date: str,
        winning_numbers: List[int],
        bonus_or_pb: Optional[int],
        board_evaluations: List[Dict[str, Any]],
        total_winnings: Decimal,
        total_cost: Decimal,
        roi_percentage: float,
    ) -> None:
        """Dispatches a rich post-draw report with official winning numbers and user board performances."""
        special_label = "PowerBall" if "POWERBALL" in game_type.upper() else "Bonus"
        special_str = f" | {special_label}: `{bonus_or_pb}`" if bonus_or_pb is not None else ""
        nums_str = ", ".join(str(n) for n in sorted(winning_numbers))

        lines = [
            f"🎰 *{game_type} Draw #{draw_number} Results ({draw_date})*",
            f"Winning Numbers: `[{nums_str}]`{special_str}\n",
        ]

        if board_evaluations:
            lines.append("🎯 *Your Generated Boards:*")
            for b in board_evaluations:
                b_id = b.get("board_id")
                b_nums = ", ".join(str(n) for n in sorted(b.get("numbers", [])))
                b_spec = b.get("bonus_or_pb")
                spec_part = f" + PB `{b_spec}`" if b_spec is not None else ""
                matched = b.get("matched_count", 0)
                prize = b.get("prize", Decimal("0.00"))
                division = b.get("division", "No Prize")
                prize_str = f" -> 🏆 *R{prize:,.2f}* ({division})" if prize > 0 else f" ({division})"
                lines.append(f"• Board #{b_id}: `[{b_nums}]`{spec_part} — {matched} matches{prize_str}")

            lines.append("")
            lines.append("📊 *Financial Summary:*")
            lines.append(f"• Cost: `R{total_cost:,.2f}` | Payout: *R{total_winnings:,.2f}*")
            lines.append(f"• Net ROI: *{roi_percentage:+.2f}%*")
        else:
            lines.append("ℹ️ _No user boards were played for this draw._")

        msg = "\n".join(lines)
        title = f"{game_type} Draw #{draw_number} Results"
        await self.broadcast(title, msg)

    async def notify_bundle_completion(
        self,
        bundle_name: str,
        target_date: str,
        sub_draws: List[Dict[str, Any]],
        board_evaluations: List[Dict[str, Any]],
        total_winnings: Decimal,
        total_cost: Decimal,
        roi_percentage: float,
    ) -> None:
        """Directive 24: one bundle-level report summing every sub-draw's prize
        against a single board cost (no per-sub-draw ROI fragmentation)."""
        title = f"{bundle_name} Results ({target_date})"
        lines = [f"🎰 *{bundle_name} Bundle Results ({target_date})*", ""]

        lines.append("🧾 *Sub-Draw Winning Numbers:*")
        for sd in sub_draws:
            game = str(sd.get("game_type", ""))
            special_label = "PowerBall" if "POWERBALL" in game.upper() else "Bonus"
            special = sd.get("bonus_or_pb")
            special_str = f" | {special_label}: `{special}`" if special is not None else ""
            nums = ", ".join(str(n) for n in sorted(sd.get("numbers", [])))
            lines.append(f"• {game} #{sd.get('draw_number')}: `[{nums}]`{special_str}")
        lines.append("")

        if board_evaluations:
            lines.append("🎯 *Your Generated Boards (bundle total):*")
            for b in board_evaluations:
                b_nums = ", ".join(str(n) for n in sorted(b.get("numbers", [])))
                b_spec = b.get("bonus_or_pb")
                spec_part = f" + PB `{b_spec}`" if b_spec is not None else ""
                board_total = b.get("board_total_prize", Decimal("0.00"))
                lines.append(f"• Board #{b.get('board_id')}: `[{b_nums}]`{spec_part}")
                for sr in b.get("sub_results", []):
                    prize = sr.get("prize", Decimal("0.00"))
                    division = sr.get("division")
                    if prize and prize > 0:
                        tail = f" -> 🏆 *R{prize:,.2f}* ({division})"
                    else:
                        tail = f" ({division})" if division else ""
                    lines.append(
                        f"    - {sr.get('game_type')}: {sr.get('matched_count', 0)} matches{tail}"
                    )
                lines.append(f"    • Board total: *R{board_total:,.2f}*")

            lines.append("")
            lines.append("📊 *Bundle Financial Summary:*")
            lines.append(f"• Cost: `R{total_cost:,.2f}` | Payout: *R{total_winnings:,.2f}*")
            lines.append(f"• Net ROI: *{roi_percentage:+.2f}%*")
        else:
            lines.append("ℹ️ _No user boards were played for this bundle._")

        await self.broadcast(title, "\n".join(lines))
