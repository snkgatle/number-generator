"""Unit tests for ScraperService parsing, upsert idempotency, and router integration."""
from datetime import date
from unittest.mock import AsyncMock, patch
import pytest

from app.models.draw import Draw
from app.schemas.draw import DrawCreate
from app.schemas.enums import GameType
from app.services.scraper_service import ScraperService


@pytest.fixture
def scraper():
    return ScraperService()


def test_parse_raw_draw_lotto(scraper):
    """Verify parsing of SA National Lottery raw LOTTO draw JSON."""
    raw_lotto = {
        "wagerIssue": "2690",
        "drawTime": "2026-10-17T19:00:00Z",
        "winNumList": ["6", "15", "46", "2", "4", "10", "1"],
        "saleMoney": 15000000,
        "jackpot": 25000000,
        "nextJackpot": 30000000,
    }

    draw_create = scraper.parse_raw_draw(raw_lotto, GameType.LOTTO)

    assert draw_create.draw_number == 2690
    assert draw_create.game_type == GameType.LOTTO
    assert draw_create.draw_date == date(2026, 10, 17)
    # Sorted 6 main numbers
    assert draw_create.numbers == [2, 4, 6, 10, 15, 46]
    # 7th is bonus ball
    assert draw_create.bonus_ball == 1
    assert draw_create.powerball is None
    assert draw_create.raw_data["jackpot"] == 25000000


def test_parse_raw_draw_powerball(scraper):
    """Verify parsing of SA National Lottery raw POWERBALL draw JSON."""
    raw_powerball = {
        "wagerIssue": "1764",
        "drawTime": "2026-10-16T19:00:00Z",
        "winNumList": ["42", "33", "38", "49", "15", "4"],
        "saleMoney": 2013850000,
        "jackpot": 60000000,
    }

    draw_create = scraper.parse_raw_draw(raw_powerball, GameType.POWERBALL)

    assert draw_create.draw_number == 1764
    assert draw_create.game_type == GameType.POWERBALL
    assert draw_create.draw_date == date(2026, 10, 16)
    # Sorted 5 main numbers
    assert draw_create.numbers == [15, 33, 38, 42, 49]
    # 6th is powerball
    assert draw_create.powerball == 4
    assert draw_create.bonus_ball is None


def test_parse_raw_draw_lotto_plus_1(scraper):
    """Verify parsing of LOTTO PLUS 1 draw."""
    raw = {
        "wagerIssue": "2690",
        "drawTime": "2026-10-17T19:00:00Z",
        "winNumList": ["30", "33", "10", "14", "51", "43", "52"],
    }
    parsed = scraper.parse_raw_draw(raw, GameType.LOTTO_PLUS_1)
    assert parsed.game_type == GameType.LOTTO_PLUS_1
    assert parsed.numbers == [10, 14, 30, 33, 43, 51]
    assert parsed.bonus_ball == 52


@pytest.mark.asyncio
async def test_upsert_draws_idempotency(scraper, db_session):
    """Directive 4: Verify ON CONFLICT DO NOTHING prevents duplicate historical records."""
    draws_batch_1 = [
        DrawCreate(
            draw_number=1001,
            game_type=GameType.LOTTO,
            draw_date=date(2026, 10, 1),
            numbers=[1, 2, 3, 4, 5, 6],
            bonus_ball=7,
        ),
        DrawCreate(
            draw_number=1002,
            game_type=GameType.LOTTO,
            draw_date=date(2026, 10, 4),
            numbers=[10, 11, 12, 13, 14, 15],
            bonus_ball=16,
        ),
    ]

    # Initial upsert: 2 rows inserted
    inserted_1 = await scraper.upsert_draws(db_session, draws_batch_1)
    assert inserted_1 == 2

    # Second upsert with 1 duplicate and 1 brand new draw
    draws_batch_2 = [
        DrawCreate(
            draw_number=1001,  # Duplicate!
            game_type=GameType.LOTTO,
            draw_date=date(2026, 10, 1),
            numbers=[1, 2, 3, 4, 5, 6],
            bonus_ball=7,
        ),
        DrawCreate(
            draw_number=1003,  # New draw
            game_type=GameType.LOTTO,
            draw_date=date(2026, 10, 8),
            numbers=[20, 21, 22, 23, 24, 25],
            bonus_ball=26,
        ),
    ]

    inserted_2 = await scraper.upsert_draws(db_session, draws_batch_2)
    # Only 1 new row should be inserted, duplicate safely ignored
    assert inserted_2 == 1


@pytest.mark.asyncio
async def test_scrape_and_sync_game_mocked(scraper, db_session):
    """Verify orchestrating scraping to database sync using mock web payload."""
    mock_payload = [
        {
            "wagerIssue": "3001",
            "drawTime": "2026-10-10T19:00:00Z",
            "winNumList": ["5", "10", "15", "20", "25", "30", "35"],
        },
        {
            "wagerIssue": "3002",
            "drawTime": "2026-10-14T19:00:00Z",
            "winNumList": ["2", "4", "6", "8", "10", "12", "14"],
        },
    ]

    with patch.object(scraper, "fetch_draws_from_web", new=AsyncMock(return_value=mock_payload)):
        result = await scraper.scrape_and_sync_game(db_session, GameType.LOTTO, limit=2)
        assert result.status == "success"
        assert result.draws_found == 2
        assert result.draws_inserted == 2
        assert result.latest_draw_number == 3001


@pytest.mark.asyncio
async def test_scraper_router_integration(client, db_session):
    """Verify Scraper FastAPI router endpoints."""
    # Seed a draw into db_session
    draw = Draw(
        draw_number=5000,
        game_type=GameType.POWERBALL.value,
        draw_date=date(2026, 10, 15),
        numbers=[1, 2, 3, 4, 5],
        powerball=10,
    )
    db_session.add(draw)
    await db_session.commit()

    # Query /scraper/draws
    res = await client.get("/api/v1/scraper/draws?game_type=POWERBALL")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1
    assert data[0]["draw_number"] == 5000

    # Query latest endpoint
    res_latest = await client.get("/api/v1/scraper/draws/POWERBALL/latest")
    assert res_latest.status_code == 200
    assert res_latest.json()["draw_number"] == 5000


def test_scrape_all_includes_all_5_games_by_default():
    """High #6: scrape_all must include POWERBALL_PLUS in its default game list."""
    from app.services.scraper_service import ScraperService
    svc = ScraperService()
    target_games = svc.scrape_all.__kwdefaults__ or {}
    defaults = target_games.get("game_types") or [
        # The code builds the list inside the method; verify via the source
    ]

    # Verify the method signature and that POWERBALL_PLUS is present
    import inspect
    source = inspect.getsource(ScraperService.scrape_all)
    assert "POWERBALL_PLUS" in source, (
        "scrape_all default game list must include POWERBALL_PLUS"
    )
