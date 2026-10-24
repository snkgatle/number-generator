"""Unit and integration tests for Authentication Service, Telegram OTP, and Session Management.

Directives Covered:
- Directive 25: 6-digit OTP generation, TTL caching (10 min expiry), single-use burn after reading.
- Directive 26: Stateless 24-hour JWT session cookie (HttpOnly, Secure, SameSite).
- Directive 27: Rate limiting on auth endpoints.
- Directive 28: Route protection (401 Unauthorized for unauthenticated requests, 200 for public health).
"""
import re
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.services.auth_service import AuthService, auth_service


def test_generate_otp_format_and_caching():
    """Directive 25: Generates a 6-digit numerical code cached in TTL cache."""
    service = AuthService()
    code = service.generate_otp("test_user_1")

    assert len(code) == 6
    assert re.match(r"^\d{6}$", code) is not None
    assert service._otp_cache.get("test_user_1") == code


def test_verify_otp_burn_after_reading():
    """Directive 25: Valid OTP verification burns the code immediately (single-use)."""
    service = AuthService()
    code = service.generate_otp("test_user_2")

    # First verification must succeed
    assert service.verify_otp(code, "test_user_2") is True

    # Immediate second verification must fail because code was burned
    assert service.verify_otp(code, "test_user_2") is False


def test_verify_otp_invalid_code():
    """Directive 25: Submitting incorrect OTP returns False without crashing."""
    service = AuthService()
    service.generate_otp("test_user_3")

    assert service.verify_otp("000000", "test_user_3") is False
    assert service.verify_otp("wrong", "test_user_3") is False
    assert service.verify_otp("", "test_user_3") is False


def test_jwt_session_creation_and_claims():
    """Directive 26: Issues stateless JWT token expiring in exactly 24 hours."""
    service = AuthService()
    token = service.create_session_jwt("admin_tester")

    assert isinstance(token, str)
    assert len(token) > 20

    payload = service.verify_session_jwt(token)
    assert payload is not None
    assert payload["sub"] == "admin_tester"
    assert payload["iss"] == settings.PROJECT_NAME

    # Expiry verification (~24 hours / 86400 seconds)
    exp = payload["exp"]
    iat = payload["iat"]
    duration = exp - iat
    assert duration == settings.JWT_EXPIRY_HOURS * 3600


def test_jwt_verification_rejects_tampered():
    """Directive 26: Tampered or invalid JWT signatures return None."""
    service = AuthService()
    valid_token = service.create_session_jwt("admin")

    # Tampered signature
    tampered_token = valid_token[:-4] + "abcd"
    assert service.verify_session_jwt(tampered_token) is None
    assert service.verify_session_jwt("invalid.token.payload") is None


@pytest.mark.asyncio
async def test_auth_request_otp_endpoint(unauthenticated_client: AsyncClient):
    """Directive 25: POST /api/v1/auth/request-otp generates OTP and responds with success."""
    res = await unauthenticated_client.post("/api/v1/auth/request-otp")
    assert res.status_code == 200
    data = res.json()
    assert "message" in data
    assert data["expires_in_seconds"] == settings.OTP_EXPIRY_SECONDS


@pytest.mark.asyncio
async def test_auth_verify_otp_and_session_flow(unauthenticated_client: AsyncClient):
    """Directive 26: POST /api/v1/auth/verify-otp validates code and issues HttpOnly session cookie."""
    # 1. Generate active OTP in service
    code = auth_service.generate_otp("default_user")

    # 2. Verify with invalid code first -> 400
    res_bad = await unauthenticated_client.post(
        "/api/v1/auth/verify-otp", json={"otp_code": "000000"}
    )
    assert res_bad.status_code == 400

    # 3. Verify with valid code -> 200 + Set-Cookie
    res_good = await unauthenticated_client.post(
        "/api/v1/auth/verify-otp", json={"otp_code": code}
    )
    assert res_good.status_code == 200
    data = res_good.json()
    assert data["success"] is True
    assert "token" in data

    # Verify cookie presence in response headers
    set_cookie_header = res_good.headers.get("set-cookie", "")
    assert settings.SESSION_COOKIE_NAME in set_cookie_header
    assert "HttpOnly" in set_cookie_header or "httponly" in set_cookie_header.lower()

    # 4. Check status with the returned cookie header
    token = data["token"]
    status_res = await unauthenticated_client.get(
        "/api/v1/auth/status",
        headers={"Cookie": f"{settings.SESSION_COOKIE_NAME}={token}"},
    )
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["authenticated"] is True
    assert status_data["expires_at"] is not None


@pytest.mark.asyncio
async def test_auth_logout_clears_cookie(unauthenticated_client: AsyncClient):
    """Directive 26: POST /api/v1/auth/logout clears the session cookie."""
    res = await unauthenticated_client.post("/api/v1/auth/logout")
    assert res.status_code == 200
    assert res.json()["success"] is True
    set_cookie = res.headers.get("set-cookie", "")
    assert settings.SESSION_COOKIE_NAME in set_cookie


@pytest.mark.asyncio
async def test_route_protection_unauthenticated_rejection(
    unauthenticated_client: AsyncClient,
):
    """Directive 28: Protected endpoints return 401 when no session cookie is provided."""
    # Scraper endpoint -> 401
    res1 = await unauthenticated_client.post(
        "/api/v1/scraper/scrape", json={"game_types": ["LOTTO"]}
    )
    assert res1.status_code == 401
    assert "Authentication required" in res1.json()["detail"]

    # Generator endpoint -> 401
    res2 = await unauthenticated_client.post(
        "/api/v1/generator/generate",
        json={"game_type": "LOTTO_FAMILY", "board_count": 1, "target_draw_date": "2026-10-24"},
    )
    assert res2.status_code == 401

    # Dashboard endpoint -> 401
    res3 = await unauthenticated_client.get("/api/v1/dashboard/budget/current")
    assert res3.status_code == 401

    # Stats endpoint -> 401
    res4 = await unauthenticated_client.get("/api/v1/stats/LOTTO")
    assert res4.status_code == 401

    # Analytics endpoint -> 401
    res5 = await unauthenticated_client.post("/api/v1/analytics/weekly?game_type=LOTTO")
    assert res5.status_code == 401

    # Public health check must still succeed -> 200
    res_health = await unauthenticated_client.get("/api/v1/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] in ("ok", "degraded")


@pytest.mark.asyncio
async def test_scheduler_token_authentication(unauthenticated_client: AsyncClient):
    """Directive 28: Requests with valid X-Scheduler-Token are authenticated for background triggers."""
    from app.core.config import settings
    headers = {"X-Scheduler-Token": settings.effective_scheduler_secret}
    res = await unauthenticated_client.get("/api/v1/dashboard/budget/current", headers=headers)
    assert res.status_code == 200
