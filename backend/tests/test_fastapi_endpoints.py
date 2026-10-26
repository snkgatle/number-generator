"""Integration tests for FastAPI endpoints."""
import pytest


@pytest.mark.asyncio
async def test_root_endpoint(client):
    """Test root endpoint returns application metadata."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "LottoMind"
    assert data["docs_url"] == "/docs"


@pytest.mark.asyncio
async def test_health_check(client):
    """Test /api/v1/health returns health status."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "project" in data


@pytest.mark.asyncio
async def test_dashboard_budget_current(client):
    """Test fetching and auto-initializing the current month's budget."""
    response = await client.get("/api/v1/dashboard/budget/current")
    assert response.status_code == 200
    data = response.json()
    assert data["total_boards"] == 20
    assert data["remaining_boards"] == 20
    assert data["is_exhausted"] is False
    assert float(data["total_budget"]) == 200.0


@pytest.mark.asyncio
async def test_circuit_breaker_endpoint(client):
    """Test circuit breaker health endpoint."""
    response = await client.get("/api/v1/dashboard/circuit-breaker")
    assert response.status_code == 200
    data = response.json()
    assert data["allowed"] is True
    assert data["remaining_boards"] == 20
    assert data["is_exhausted"] is False


@pytest.mark.asyncio
async def test_scraper_trigger(client):
    """Test manual scraper trigger returns 200 with ScrapeResponse."""
    from unittest.mock import AsyncMock, patch
    from app.schemas.draw import ScrapeResponse

    mock_resp = ScrapeResponse(
        status="completed",
        total_found=40,
        total_inserted=40,
        details=[],
        message="Scrape complete",
    )
    with patch("app.api.v1.scraper.scraper_service.scrape_all", new=AsyncMock(return_value=mock_resp)):
        response = await client.post("/api/v1/scraper/scrape")
        assert response.status_code == 200
        assert response.json()["status"] == "completed"
        assert response.json()["total_inserted"] == 40


@pytest.mark.asyncio
async def test_generator_trigger(client):
    """Test generator endpoint returns 201 Created with generated boards."""
    from unittest.mock import patch
    from app.schemas.board import AIBoardRecommendation, AIGenerationResponse
    from app.schemas.enums import GameType

    mock_ai = AIGenerationResponse(
        game_type=GameType.LOTTO,
        boards=[
            AIBoardRecommendation(
                numbers=[1, 2, 3, 4, 5, 6],
                bonus_or_powerball=None,
                confidence_score=75.0,
                reasoning="Standard test board.",
            )
        ],
        statistical_analysis_summary="Summary",
    )
    with patch("app.api.v1.generator.ai_service.generate_boards", return_value=mock_ai):
        response = await client.post(
            "/api/v1/generator/generate",
            json={"game_type": "LOTTO", "allocated_boards": 1},
        )
        assert response.status_code == 201
        data = response.json()
        assert len(data) == 1
        assert data[0]["bundle_name"] == "LOTTO_FAMILY"
        # Directive 20: EV score must be computed and persisted on creation
        assert data[0]["ev_score"] is not None
        assert 0.0 <= data[0]["ev_score"] <= 100.0


@pytest.mark.asyncio
async def test_board_played_toggle(client, db_session):
    """Directive 10: PATCH /boards/{id}/played toggles PENDING <-> PLAYED with played_at."""
    from datetime import date
    from decimal import Decimal
    from app.models.board import GeneratedBoard

    board = GeneratedBoard(
        bundle_name="LOTTO_FAMILY",
        game_type="LOTTO_FAMILY",
        target_draw_date=date(2026, 10, 28),
        numbers=[4, 12, 19, 23, 44, 51],
        confidence_score=85.0,
        cost=Decimal("10.00"),
        status="PENDING",
    )
    db_session.add(board)
    await db_session.commit()
    await db_session.refresh(board)

    # Mark as played
    res = await client.patch(f"/api/v1/generator/boards/{board.id}/played")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "PLAYED"
    assert data["played_at"] is not None

    # Toggle back to pending
    res2 = await client.patch(f"/api/v1/generator/boards/{board.id}/played")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["status"] == "PENDING"
    assert data2["played_at"] is None


def test_setup_logging():
    """Test Loguru initialization and logger interceptor."""
    import logging
    from app.core.logging import setup_logging
    from loguru import logger

    setup_logging()
    # Test logging via standard library and loguru
    std_logger = logging.getLogger("uvicorn.error")
    std_logger.info("Test intercepted log message")
    logger.info("Direct loguru test message")


@pytest.mark.asyncio
async def test_stats_deltas_endpoint(client):
    """Test /api/v1/stats/{game_type}/deltas returns DeltaDistributionReport."""
    response = await client.get("/api/v1/stats/LOTTO/deltas?sample_size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["game_type"] == "LOTTO"
    assert "mean_delta" in data
    assert "top_deltas" in data


@pytest.mark.asyncio
async def test_stats_positional_endpoint(client):
    """Test /api/v1/stats/{game_type}/positional returns PositionalFrequencyReport."""
    response = await client.get("/api/v1/stats/LOTTO/positional?sample_size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["game_type"] == "LOTTO"
    assert "positions" in data
    assert "structural_validity_bounds" in data


@pytest.mark.asyncio
async def test_stats_markov_endpoint(client):
    """Test /api/v1/stats/{game_type}/markov returns MarkovChainReport."""
    response = await client.get("/api/v1/stats/LOTTO/markov?sample_size=10&alpha=1.0")
    assert response.status_code == 200
    data = response.json()
    assert data["game_type"] == "LOTTO"
    assert data["alpha"] == 1.0
    assert "top_transition_candidates" in data


@pytest.mark.asyncio
async def test_stats_ev_score_endpoint(client):
    """Test /api/v1/stats/ev-score calculates Expected Value penalty report."""
    response = await client.post(
        "/api/v1/stats/ev-score",
        json={"numbers": [4, 12, 19, 23, 44, 51]},
    )
    assert response.status_code == 200
    data = response.json()
    assert "ev_score" in data
    assert "is_human_biased" in data
    assert "calendar_count" in data


@pytest.mark.asyncio
async def test_cors_headers_on_origin(client):
    """Test CORS headers are returned for configured origin."""
    response = await client.get(
        "/api/v1/health",
        headers={"Origin": "https://lotto-num-gen-33fe8.uc.r.appspot.com"},
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://lotto-num-gen-33fe8.uc.r.appspot.com"
    assert response.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.asyncio
async def test_global_exception_handler_cors():
    """Test unhandled 500 exceptions still return CORS headers for browser compatibility."""
    from unittest.mock import patch
    from httpx import ASGITransport, AsyncClient
    from app.main import app

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch("app.api.v1.api.check_db_connection", side_effect=RuntimeError("Simulated DB failure")):
            response = await ac.get(
                "/api/v1/health",
                headers={"Origin": "https://lotto-num-gen-33fe8.uc.r.appspot.com"},
            )
            assert response.status_code == 500
            assert response.headers.get("access-control-allow-origin") == "https://lotto-num-gen-33fe8.uc.r.appspot.com"
            assert response.headers.get("access-control-allow-credentials") == "true"
            data = response.json()
            assert data["detail"] == "An internal server error occurred."
            assert data["error_type"] == "RuntimeError"



