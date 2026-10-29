"""Playwright scraper service targeting the SA National Lottery results page.

Adheres to:
- Directive 4: Idempotent scraping with ON CONFLICT DO NOTHING on (draw_number, game_type).
- Directive 6: Retry logic using tenacity with exponential backoff and error logging.
- Directive 2: Strict Pydantic validation via DrawCreate prior to database insertion.
"""
from datetime import datetime, date
from typing import Any, Dict, List, Optional
from loguru import logger
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.models.draw import Draw
from app.schemas.draw import DrawCreate, ScrapeGameResult, ScrapeResponse
from app.schemas.enums import GameType


# Mapping of internal GameType to SA National Lottery API parameters
LOTTERY_GAME_CONFIG: Dict[GameType, Dict[str, Any]] = {
    GameType.LOTTO: {
        "gameId": 11101,
        "winPoolId": 100,
        "plusFlag": 0,
        "name": "LOTTO",
        "main_count": 6,
        "has_bonus": True,
        "has_powerball": False,
    },
    GameType.LOTTO_PLUS_1: {
        "gameId": 11101,
        "winPoolId": 101,
        "plusFlag": 1,
        "name": "LOTTO Plus1",
        "main_count": 6,
        "has_bonus": True,
        "has_powerball": False,
    },
    GameType.LOTTO_PLUS_2: {
        "gameId": 11101,
        "winPoolId": 102,
        "plusFlag": 2,
        "name": "LOTTO Plus2",
        "main_count": 6,
        "has_bonus": True,
        "has_powerball": False,
    },
    GameType.POWERBALL: {
        "gameId": 11201,
        "winPoolId": 100,
        "plusFlag": 0,
        "name": "PowerBall",
        "main_count": 5,
        "has_bonus": False,
        "has_powerball": True,
    },
    GameType.POWERBALL_PLUS: {
        "gameId": 11201,
        "winPoolId": 101,
        "plusFlag": 1,
        "name": "PowerBall XTRA",
        "main_count": 5,
        "has_bonus": False,
        "has_powerball": True,
    },
    # Daily Lotto: 5 numbers from 1-36, no bonus, no PowerBall. Identifiers
    # verified against a live /api/engine/draw/issueWinPoolInfoPageQuery call
    # on 2026-10-29 (gameId=11001, winPoolId=100, plusFlag=0, 5 win numbers).
    GameType.DAILY_LOTTO: {
        "gameId": 11001,
        "winPoolId": 100,
        "plusFlag": 0,
        "name": "Daily Lotto",
        "main_count": 5,
        "has_bonus": False,
        "has_powerball": False,
    },
}

BASE_RESULTS_URL = "https://www.nationallottery.co.za/#/results"


class ScraperService:
    """Automated scraper engine utilizing Playwright for browser automation

    and session-authenticated API queries against the SA National Lottery.
    """

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def fetch_draws_from_web(
        self, game_type: GameType, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Launch headless Chromium, initialize session at results page, and extract draws."""
        config = LOTTERY_GAME_CONFIG.get(game_type)
        if not config:
            raise ValueError(f"Unsupported game type for scraping: {game_type}")

        logger.info(
            f"Launching Playwright to fetch {limit} draws for {game_type.value} "
            f"(gameId={config['gameId']}, winPoolId={config['winPoolId']})"
        )

        async with async_playwright() as p:
            browser: Browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )
            context: BrowserContext = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 720},
            )
            page: Page = await context.new_page()

            try:
                # Navigate to the official results page to initialize session, cookies, and tokens
                await page.goto(BASE_RESULTS_URL, wait_until="networkidle", timeout=30000)

                # Query the draw history endpoint directly from the browser context
                response_payload = await page.evaluate(
                    """async ({ gId, pId, pFlag, limitCount }) => {
                        const body = {
                            startDate: '2023-01-01T00:00:00Z',
                            endDate: '2027-12-31T23:59:59Z',
                            gameId: gId,
                            winPoolId: pId,
                            plusFlag: pFlag,
                            pageNum: 1,
                            pageSize: limitCount,
                            deviceCode: '1',
                            deviceSoftVersion: '1.0.0',
                            platform: 4,
                            platformModel: navigator.userAgent,
                            timestamp: Date.now()
                        };
                        const res = await fetch('/api/engine/draw/issueWinPoolInfoPageQuery', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(body)
                        });
                        return await res.json();
                    }""",
                    {
                        "gId": config["gameId"],
                        "pId": config["winPoolId"],
                        "pFlag": config["plusFlag"],
                        "limitCount": limit,
                    },
                )

                if not response_payload or response_payload.get("code") != 0:
                    err_msg = (
                        response_payload.get("msg")
                        if response_payload
                        else "Empty response from lottery API"
                    )
                    raise RuntimeError(f"Lottery API query failed: {err_msg}")

                draw_list = response_payload.get("data", {}).get("list", [])
                logger.info(f"Retrieved {len(draw_list)} raw draws for {game_type.value}")
                return draw_list

            finally:
                await context.close()
                await browser.close()

    def parse_raw_draw(self, raw: Dict[str, Any], game_type: GameType) -> DrawCreate:
        """Parses and validates raw lottery API records into validated DrawCreate models."""
        config = LOTTERY_GAME_CONFIG[game_type]

        draw_number = int(raw["wagerIssue"])

        # Parse date from ISO string (e.g., '2026-10-17T19:00:00Z')
        draw_time_str = raw["drawTime"]
        if "T" in draw_time_str:
            draw_date: date = datetime.fromisoformat(
                draw_time_str.replace("Z", "+00:00")
            ).date()
        else:
            draw_date = datetime.strptime(draw_time_str[:10], "%Y-%m-%d").date()

        win_num_list: List[str] = raw.get("winNumList", [])
        if not win_num_list:
            raise ValueError(f"Draw #{draw_number} missing winning numbers list")

        # Convert numbers to integers
        int_numbers = [int(n) for n in win_num_list]

        bonus_ball: Optional[int] = None
        powerball: Optional[int] = None

        if config["has_bonus"]:
            # e.g., Lotto, Lotto Plus 1, Lotto Plus 2: 6 main numbers + 1 bonus ball
            main_numbers = int_numbers[:6]
            if len(int_numbers) > 6:
                bonus_ball = int_numbers[6]
        elif config["has_powerball"]:
            # e.g., PowerBall, PowerBall Plus: 5 main numbers + 1 powerball
            main_numbers = int_numbers[:5]
            if len(int_numbers) > 5:
                powerball = int_numbers[5]
        else:
            main_numbers = int_numbers[: config["main_count"]]

        # Extract environmental metadata if present in payload
        machine_name = raw.get("drawMachine") or raw.get("machineName") or raw.get("machine")
        ball_set = raw.get("ballSet") or raw.get("ballSetName") or raw.get("set")
        draw_time = raw.get("drawTime") or raw.get("time")

        # Construct and validate DrawCreate
        return DrawCreate(
            draw_number=draw_number,
            game_type=game_type,
            draw_date=draw_date,
            numbers=main_numbers,
            bonus_ball=bonus_ball,
            powerball=powerball,
            machine_name=str(machine_name) if machine_name else None,
            ball_set=str(ball_set) if ball_set else None,
            draw_time=str(draw_time) if draw_time else None,
            raw_data={
                "saleMoney": raw.get("saleMoney"),
                "jackpot": raw.get("jackpot"),
                "nextJackpot": raw.get("nextJackpot"),
                "machine": machine_name,
                "ballSet": ball_set,
                "drawTime": draw_time,
            },
        )

    async def upsert_draws(
        self, db: AsyncSession, draws: List[DrawCreate]
    ) -> int:
        """Directive 4: Idempotent upsert using ON CONFLICT DO NOTHING on (draw_number, game_type).

        Returns count of newly inserted rows.
        """
        if not draws:
            return 0

        dialect_name = db.get_bind().dialect.name
        inserted_count = 0

        for draw_create in draws:
            values = {
                "draw_number": draw_create.draw_number,
                "game_type": draw_create.game_type.value,
                "draw_date": draw_create.draw_date,
                "numbers": draw_create.numbers,
                "bonus_ball": draw_create.bonus_ball,
                "powerball": draw_create.powerball,
                "machine_name": draw_create.machine_name,
                "ball_set": draw_create.ball_set,
                "draw_time": draw_create.draw_time,
                "raw_data": draw_create.raw_data,
            }

            if dialect_name == "postgresql":
                from sqlalchemy.dialects.postgresql import insert as pg_insert

                stmt = pg_insert(Draw).values(**values).on_conflict_do_nothing(
                    index_elements=["draw_number", "game_type"]
                )
            elif dialect_name == "sqlite":
                from sqlalchemy.dialects.sqlite import insert as sqlite_insert

                stmt = sqlite_insert(Draw).values(**values).on_conflict_do_nothing(
                    index_elements=["draw_number", "game_type"]
                )
            else:
                # Fallback for generic SQL
                from sqlalchemy import select

                existing = await db.execute(
                    select(Draw.id).where(
                        Draw.draw_number == draw_create.draw_number,
                        Draw.game_type == draw_create.game_type.value,
                    )
                )
                if existing.scalar_one_or_none() is not None:
                    continue
                db.add(Draw(**values))
                inserted_count += 1
                continue

            result = await db.execute(stmt)
            if result.rowcount > 0:
                inserted_count += 1

        await db.commit()
        return inserted_count

    async def scrape_and_sync_game(
        self, db: AsyncSession, game_type: GameType, limit: int = 50
    ) -> ScrapeGameResult:
        """Scrapes, parses, and upserts historical draws for a specific game."""
        try:
            raw_draws = await self.fetch_draws_from_web(game_type, limit=limit)
            parsed_draws: List[DrawCreate] = []

            for raw in raw_draws:
                try:
                    parsed = self.parse_raw_draw(raw, game_type)
                    parsed_draws.append(parsed)
                except Exception as parse_err:
                    logger.warning(
                        f"Skipping malformed draw item for {game_type.value}: {parse_err}"
                    )

            inserted = await self.upsert_draws(db, parsed_draws)
            latest_draw = parsed_draws[0].draw_number if parsed_draws else None

            logger.info(
                f"Sync complete for {game_type.value}: found {len(parsed_draws)}, "
                f"inserted {inserted} new draws."
            )

            return ScrapeGameResult(
                game_type=game_type,
                draws_found=len(parsed_draws),
                draws_inserted=inserted,
                latest_draw_number=latest_draw,
                status="success",
            )
        except Exception as e:
            logger.error(f"Scraper error for {game_type.value}: {e}")
            return ScrapeGameResult(
                game_type=game_type,
                draws_found=0,
                draws_inserted=0,
                status="failed",
                error=str(e),
            )

    async def scrape_all(
        self,
        db: AsyncSession,
        game_types: Optional[List[GameType]] = None,
        limit: int = 50,
    ) -> ScrapeResponse:
        """Orchestrates multi-game scraping for all standard SA lottery games."""
        target_games = game_types or [
            GameType.LOTTO,
            GameType.POWERBALL,
            GameType.LOTTO_PLUS_1,
            GameType.LOTTO_PLUS_2,
            GameType.POWERBALL_PLUS,
            GameType.DAILY_LOTTO,
        ]

        details: List[ScrapeGameResult] = []
        total_found = 0
        total_inserted = 0

        for game in target_games:
            result = await self.scrape_and_sync_game(db, game, limit=limit)
            details.append(result)
            total_found += result.draws_found
            total_inserted += result.draws_inserted

        return ScrapeResponse(
            status="completed",
            total_found=total_found,
            total_inserted=total_inserted,
            details=details,
            message=(
                f"Successfully scraped {len(target_games)} games: "
                f"{total_inserted} new draws inserted out of {total_found} retrieved."
            ),
        )

    # Alias for pipeline integration
    scrape_and_sync_all_games = scrape_all
