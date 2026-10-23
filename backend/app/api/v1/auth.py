"""Authentication API Endpoints for Passwordless Telegram OTP and Session Management.

Directives:
- Directive 25: Request and verify single-use 6-digit OTP delivered via Telegram Bot API.
- Directive 26: Issue 24-hour JWT session cookie (HttpOnly, Secure, SameSite).
- Directive 27: Rate limiting (1 OTP request/min, 5 verifications/hr per IP).
"""
from datetime import datetime, timezone
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from loguru import logger
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.security import get_optional_user
from app.schemas.auth import AuthStatusResponse, OTPRequestResponse, OTPVerifyRequest
from app.services.auth_service import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Rate limiter keyed by client remote IP (Directive 27)
limiter = Limiter(key_func=get_remote_address)


@router.post(
    "/request-otp",
    response_model=OTPRequestResponse,
    summary="Request Telegram OTP",
    description="Generates a 6-digit OTP code and dispatches it via Telegram Bot API (Directive 25). Rate limited to 1 request/min.",
)
@limiter.limit("1/minute")
async def request_otp(request: Request) -> OTPRequestResponse:
    """Dispatches a single-use OTP code to the authorized Telegram chat."""
    logger.info(f"OTP request initiated from client IP: {get_remote_address(request)}")

    sent = await auth_service.request_and_send_otp("default_user")

    if not sent:
        # Note: If Telegram is unconfigured or fails, OTP is still generated for testing
        return OTPRequestResponse(
            message="OTP generated. (Telegram delivery unconfigured or pending)",
            expires_in_seconds=settings.OTP_EXPIRY_SECONDS,
        )

    return OTPRequestResponse(
        message="A 6-digit verification code has been sent to your Telegram.",
        expires_in_seconds=settings.OTP_EXPIRY_SECONDS,
    )


@router.post(
    "/verify-otp",
    summary="Verify OTP and Establish Session",
    description="Validates the 6-digit OTP and issues a 24-hour JWT session cookie (Directive 26). Rate limited to 5 verifications/hr.",
)
@limiter.limit("5/hour")
async def verify_otp(
    payload: OTPVerifyRequest, request: Request, response: Response
) -> Dict[str, Any]:
    """Verifies the submitted OTP code and sets the session cookie upon success."""
    logger.info(f"OTP verification attempt from client IP: {get_remote_address(request)}")

    is_valid = auth_service.verify_otp(payload.otp_code, "default_user")
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP code. Please request a new code.",
        )

    # Issue 24-hour JWT session (Directive 26)
    token = auth_service.create_session_jwt("admin")

    # Set HttpOnly, Secure cookie
    max_age_seconds = settings.JWT_EXPIRY_HOURS * 3600
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=token,
        max_age=max_age_seconds,
        expires=max_age_seconds,
        httponly=True,
        secure=settings.is_cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )

    logger.info("Session successfully established. Cookie dispatched.")
    return {
        "success": True,
        "message": "Authentication successful. Session active for 24 hours.",
        "token": token,
        "expires_in_hours": settings.JWT_EXPIRY_HOURS,
    }


@router.post(
    "/logout",
    summary="Logout and Clear Session",
    description="Clears the HttpOnly JWT session cookie.",
)
async def logout(response: Response) -> Dict[str, Any]:
    """Deletes the session cookie to conclude user session."""
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
        secure=settings.is_cookie_secure,
        samesite=settings.cookie_samesite,
    )
    logger.info("User logged out; session cookie cleared.")
    return {"success": True, "message": "Logged out successfully."}


@router.get(
    "/status",
    response_model=AuthStatusResponse,
    summary="Check Authentication Status",
    description="Returns whether the caller holds an active, valid JWT session.",
)
async def auth_status(
    user_payload: Dict[str, Any] = Depends(get_optional_user),
) -> AuthStatusResponse:
    """Checks the validity of the current session cookie."""
    if not user_payload:
        return AuthStatusResponse(
            authenticated=False,
            message="No active session found.",
        )

    exp_timestamp = user_payload.get("exp")
    expires_at = (
        datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        if exp_timestamp
        else None
    )

    return AuthStatusResponse(
        authenticated=True,
        expires_at=expires_at,
        message="Session active.",
    )
