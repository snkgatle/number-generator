"""Pydantic schemas for passwordless Telegram OTP and session authentication."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class OTPRequestResponse(BaseModel):
    """Response returned when an OTP has been dispatched to Telegram."""
    message: str = Field(
        default="OTP has been dispatched via Telegram.",
        description="User notification message",
    )
    expires_in_seconds: int = Field(
        default=600,
        description="Duration in seconds before the OTP expires (10 minutes)",
    )


class OTPVerifyRequest(BaseModel):
    """Payload to verify an incoming 6-digit OTP code."""
    otp_code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
        description="6-digit numerical OTP code received via Telegram",
    )


class AuthStatusResponse(BaseModel):
    """User authentication status response."""
    authenticated: bool = Field(
        ...,
        description="True if the caller possesses an active, valid JWT session",
    )
    expires_at: Optional[datetime] = Field(
        default=None,
        description="ISO timestamp when the current session expires",
    )
    message: Optional[str] = Field(
        default=None,
        description="Descriptive status message",
    )
