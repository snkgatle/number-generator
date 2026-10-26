"""FastAPI Security Dependencies for JWT Session Cookie Verification.

Directives:
- Directive 26: Session Management via HttpOnly, Secure, SameSite=Strict cookie with 24-hour expiration.
- Directive 28: Route Protection: All existing /api/v1/ endpoints must require the JWT dependency and return 401.
"""
import hmac
import secrets
from typing import Any, Dict, Optional
from fastapi import Cookie, Depends, HTTPException, Header, Request, status
from loguru import logger

from app.core.config import settings
from app.services.auth_service import auth_service


async def get_token_from_request(
    request: Request,
    session_cookie: Optional[str] = Cookie(default=None, alias=settings.SESSION_COOKIE_NAME),
    authorization: Optional[str] = Header(default=None),
) -> Optional[str]:
    """Extracts the session token from HttpOnly cookie or Authorization Bearer header."""
    # 1. Check HttpOnly cookie (Directive 26 primary mechanism)
    if session_cookie:
        return session_cookie

    # Also check request.cookies directly in case alias parsing had edge cases
    raw_cookie = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if raw_cookie:
        return raw_cookie

    # 2. Check Authorization Bearer header (optional client fallback)
    if authorization and authorization.startswith("Bearer "):
        return authorization.split(" ", 1)[1].strip()

    return None


async def require_authenticated_user(
    token: Optional[str] = Depends(get_token_from_request),
    scheduler_token: Optional[str] = Header(default=None, alias="X-Scheduler-Token"),
) -> Dict[str, Any]:
    """Dependency enforcing that callers possess a valid session or scheduler credential.

    Directive 28:
    - User requests must provide a valid 24h JWT session (cookie or Authorization Bearer).
    - Automated cloud scheduler triggers may provide X-Scheduler-Token or Google Service Account OIDC token.
    - Unauthenticated requests return HTTP 401.
    """
    secret = settings.effective_scheduler_secret

    # 1. Check custom X-Scheduler-Token header (constant-time comparison)
    if scheduler_token and secret and hmac.compare_digest(scheduler_token, secret):
        logger.debug("Access granted via X-Scheduler-Token header.")
        return {"sub": "cloud-scheduler", "role": "scheduler"}

    # 2. Check if token matches scheduler secret directly (constant-time comparison)
    if token and secret and hmac.compare_digest(token, secret):
        logger.debug("Access granted via Bearer scheduler secret.")
        return {"sub": "cloud-scheduler", "role": "scheduler"}

    # 3. Check Google Cloud Service Account OIDC token (from Cloud Scheduler)
    if token and settings.SCHEDULER_AUDIENCE:
        try:
            from google.oauth2 import id_token
            from google.auth.transport import requests as google_requests

            # Verify the token signature, issuer, and expiration using Google's public keys
            request_adapter = google_requests.Request()
            claims = id_token.verify_oauth2_token(
                token, request_adapter, settings.SCHEDULER_AUDIENCE
            )

            # Verify issuer is Google
            issuer = claims.get("iss", "")
            if issuer not in ("https://accounts.google.com", "accounts.google.com"):
                logger.warning(f"OIDC token has invalid issuer: {issuer}")
            else:
                # Verify email is a Google service account
                email = claims.get("email", "")
                if email.endswith("@developer.gserviceaccount.com") or email.endswith(
                    "@appspot.gserviceaccount.com"
                ):
                    logger.info(f"Access granted to Google Service Account OIDC token: {email}")
                    return {"sub": email, "role": "scheduler"}
                else:
                    logger.warning(f"OIDC token email is not a service account: {email}")
        except Exception as exc:
            # Token verification failed - continue to session JWT check
            logger.debug(f"Google OIDC token verification failed: {exc}")

    # 4. Standard User Session JWT Verification (Directive 26)
    if not token:
        logger.debug("Access denied: No session token provided in cookie or header.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in with a valid OTP.",
            headers={"WWW-Authenticate": "Cookie"},
        )

    payload = auth_service.verify_session_jwt(token)
    if not payload:
        logger.debug("Access denied: Session token is expired or invalid.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid. Please re-authenticate.",
            headers={"WWW-Authenticate": "Cookie"},
        )

    return payload


async def get_optional_user(
    token: Optional[str] = Depends(get_token_from_request),
) -> Optional[Dict[str, Any]]:
    """Dependency that inspects the session without rejecting unauthenticated callers."""
    if not token:
        return None
    return auth_service.verify_session_jwt(token)
