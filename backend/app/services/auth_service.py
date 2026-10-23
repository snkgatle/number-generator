"""Authentication Service implementing Telegram OTP and stateless JWT session management.

Directives:
- Directive 25: 6-digit OTP generated via `secrets`, stored in TTL cache (10 min expiry), sent via Telegram.
- Directive 26: Stateless 24-hour JWT stored in HttpOnly, Secure, SameSite=Strict cookie. No PostgreSQL sessions.
"""
from datetime import datetime, timedelta, timezone
import secrets
from typing import Any, Dict, Optional
from cachetools import TTLCache
from jose import JWTError, jwt
from loguru import logger

from app.core.config import settings
from app.services.notifier import Notifier


class AuthService:
    """Handles passwordless OTP generation/verification and stateless JWT creation."""

    def __init__(self, notifier: Optional[Notifier] = None):
        self.notifier = notifier or Notifier()
        # TTL Cache: max 100 entries, expires in OTP_EXPIRY_SECONDS (default 600s / 10m)
        self._otp_cache: TTLCache[str, str] = TTLCache(
            maxsize=100, ttl=settings.OTP_EXPIRY_SECONDS
        )

    def generate_otp(self, identifier: str = "default_user") -> str:
        """Generates a cryptographically secure 6-digit numerical OTP and caches it with TTL."""
        # 6-digit zero-padded number using secrets.randbelow(1_000_000)
        code = f"{secrets.randbelow(1_000_000):06d}"
        self._otp_cache[identifier] = code
        logger.info(f"Generated 6-digit OTP for identifier '{identifier}' (expires in {settings.OTP_EXPIRY_SECONDS}s).")
        return code

    async def request_and_send_otp(self, identifier: str = "default_user") -> bool:
        """Generates an OTP and dispatches it via Telegram Bot API."""
        otp_code = self.generate_otp(identifier)
        sent = await self.notifier.send_telegram_otp(otp_code)
        if not sent:
            logger.warning(
                "Telegram dispatch failed or Telegram not configured. "
                "OTP generated and retained in TTL cache for local verification."
            )
        return sent

    def verify_otp(self, otp_code: str, identifier: str = "default_user") -> bool:
        """Verifies the OTP code against TTL cache and burns it immediately (single-use)."""
        cached_code = self._otp_cache.get(identifier)
        if not cached_code:
            logger.warning(f"OTP verification failed for '{identifier}': Code expired or not requested.")
            return False

        # Constant-time comparison to prevent timing attacks
        if secrets.compare_digest(cached_code, otp_code.strip()):
            # Burn after reading (Directive 25 single-use security)
            del self._otp_cache[identifier]
            logger.info(f"OTP successfully verified and burned for '{identifier}'.")
            return True

        logger.warning(f"OTP verification failed for '{identifier}': Invalid code provided.")
        return False

    def create_session_jwt(self, subject: str = "admin") -> str:
        """Creates a stateless JWT session token expiring in exactly 24 hours (Directive 26)."""
        now = datetime.now(timezone.utc)
        expire = now + timedelta(hours=settings.JWT_EXPIRY_HOURS)

        payload: Dict[str, Any] = {
            "sub": subject,
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
            "iss": settings.PROJECT_NAME,
        }

        token = jwt.encode(
            payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
        )
        return token

    def verify_session_jwt(self, token: str) -> Optional[Dict[str, Any]]:
        """Verifies and decodes a session JWT. Returns payload if valid, None otherwise."""
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
                issuer=settings.PROJECT_NAME,
            )
            return payload
        except JWTError as exc:
            logger.debug(f"JWT verification rejected: {exc}")
            return None


# Global service singleton
auth_service = AuthService()
