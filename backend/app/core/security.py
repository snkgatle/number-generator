"""FastAPI Security Dependencies for JWT Session Cookie Verification.

Directives:
- Directive 26: Session Management via HttpOnly, Secure, SameSite=Strict cookie with 24-hour expiration.
- Directive 28: Route Protection: All existing /api/v1/ endpoints must require the JWT dependency and return 401.
"""
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
) -> Dict[str, Any]:
    """Dependency enforcing that callers possess a valid 24h JWT session.

    Directive 28: Unauthenticated requests must return HTTP 401.
    """
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
