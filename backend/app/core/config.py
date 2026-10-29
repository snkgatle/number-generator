"""Application configuration using Pydantic Settings."""
from typing import List, Optional
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import json


class Settings(BaseSettings):
    """LottoMind application settings loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # General
    PROJECT_NAME: str = "LottoMind"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # Database (PostgreSQL via asyncpg)
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/lottomind",
        description="Async PostgreSQL connection URL",
    )

    # Alibaba Cloud DashScope (Qwen-Max)
    DASHSCOPE_API_KEY: Optional[str] = Field(
        default=None,
        description="API key for Alibaba Cloud DashScope SDK",
    )
    DASHSCOPE_BASE_URL: str = Field(
        default="https://maas.qwencloudapi.com/compatible-mode/v1",
        description="Base URL for Qwen OpenAPI/DashScope compatible endpoint",
    )
    QWEN_MODEL: str = Field(
        default="qwen-max",
        description="Target model identifier for board generation",
    )
    QWEN_ANALYTICS_MODEL: str = Field(
        default="qwen3.8-flash",
        description="Target model identifier for temporal analytics and pattern reviews",
    )

    # Budget & Allocation Rules (Directive 23: pooled budgets, isolated per family)
    DEFAULT_MONTHLY_BUDGET: float = Field(
        default=200.00,
        description="Default monthly bundle budget in ZAR (alias of BUNDLE_MONTHLY_BUDGET)",
    )
    BUNDLE_MONTHLY_BUDGET: float = Field(
        default=200.00,
        description="Monthly budget pool for Lotto/PowerBall bundles in ZAR",
    )
    DAILY_LOTTO_MONTHLY_BUDGET: float = Field(
        default=50.00,
        description="Monthly budget pool for Daily Lotto in ZAR",
    )
    COST_PER_BOARD: float = Field(
        default=10.00,
        description="Cost in ZAR per bundled board generated (Directive 23)",
    )
    DAILY_LOTTO_COST_PER_BOARD: float = Field(
        default=3.00,
        description="Cost in ZAR per Daily Lotto board",
    )
    TOTAL_MONTHLY_BOARDS: int = Field(
        default=20,
        description="Default max bundle boards per month (200 / 10 = 20) (Directive 23)",
    )
    BUDGET_CYCLE_ROLLOVER_DAY: int = Field(
        default=25,
        description="Day of month when budget cycle initializes (default 25th)",
    )

    # Performance Feedback / Outcome Calibration
    FEEDBACK_WINDOW_SIZE: int = Field(
        default=10,
        description="Number of most recent evaluated draws in the rolling feedback window",
    )
    FEEDBACK_MIN_SAMPLES: int = Field(
        default=8,
        description="Minimum complete feedback records before outcome calibration is considered sufficient",
    )
    FEEDBACK_PROMPT_ENABLED: bool = Field(
        default=True,
        description="Inject realized-outcome calibration into future Qwen generation prompts",
    )
    FEEDBACK_ALLOCATION_ENABLED: bool = Field(
        default=False,
        description="Allow realized positive ROI to grant at most one additional board (opt-in)",
    )

    # Alerts & Notifications (Phase 5.5)
    TELEGRAM_BOT_TOKEN: Optional[str] = Field(
        default=None,
        description="Optional Telegram Bot token for push notifications",
    )
    TELEGRAM_CHAT_ID: Optional[str] = Field(
        default=None,
        description="Optional Telegram Chat ID to receive alerts",
    )
    DISCORD_WEBHOOK_URL: Optional[str] = Field(
        default=None,
        description="Optional Discord Webhook URL for channel notifications",
    )

    # Authentication & Session Security (Phase 1.2 / Directives 25-28)
    JWT_SECRET_KEY: str = Field(
        default="lottomind-insecure-dev-secret-key-change-in-production-min32chars",
        description="Secret key for signing stateless JWT session cookies",
    )
    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="JWT signing algorithm",
    )
    JWT_EXPIRY_HOURS: int = Field(
        default=24,
        description="JWT token validity in hours (Directive 26: exactly 24 hours)",
    )
    OTP_EXPIRY_SECONDS: int = Field(
        default=600,
        description="OTP validity in seconds (Directive 25: 10 min expiry)",
    )
    SESSION_COOKIE_NAME: str = Field(
        default="lottomind_session",
        description="HttpOnly cookie key used to store the user session JWT",
    )
    SESSION_COOKIE_SECURE: Optional[bool] = Field(
        default=None,
        description="Enforces Secure flag on session cookie (auto-enabled in production)",
    )
    SCHEDULER_SECRET: Optional[str] = Field(
        default=None,
        description="Shared secret for authenticating Google Cloud Scheduler HTTP triggers (Directive 28)",
    )
    SCHEDULER_AUDIENCE: Optional[str] = Field(
        default=None,
        description="Expected audience for Google Cloud Scheduler OIDC tokens (typically the Cloud Run service URL)",
    )

    @property
    def effective_scheduler_secret(self) -> str:
        """Returns SCHEDULER_SECRET if set, falling back to JWT_SECRET_KEY."""
        return self.SCHEDULER_SECRET or self.JWT_SECRET_KEY

    @property
    def is_cookie_secure(self) -> bool:
        """Determines if the session cookie must have Secure=True."""
        if self.SESSION_COOKIE_SECURE is not None:
            return self.SESSION_COOKIE_SECURE
        return self.ENVIRONMENT.lower() == "production"

    @property
    def cookie_samesite(self) -> str:
        """SameSite cookie policy: 'none' for cross-origin production HTTPS, 'lax' for local dev."""
        return "none" if self.is_cookie_secure else "lax"

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://lotto-num-gen-33fe8.uc.r.appspot.com",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return []

    @model_validator(mode="after")
    def guard_default_secrets_in_production(self):
        """Refuse to start in production with the insecure default JWT secret key."""
        if self.ENVIRONMENT.lower() == "production":
            if self.JWT_SECRET_KEY == "lottomind-insecure-dev-secret-key-change-in-production-min32chars":
                raise ValueError(
                    "JWT_SECRET_KEY must be changed from the default value in production."
                )
        return self


settings = Settings()
