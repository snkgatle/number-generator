"""Application configuration using Pydantic Settings."""
from typing import List, Optional
from pydantic import Field, field_validator
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

    # Budget & Allocation Rules (Directive 23: R10/board = 20 boards/month)
    DEFAULT_MONTHLY_BUDGET: float = Field(
        default=200.00,
        description="Default monthly budget in ZAR",
    )
    COST_PER_BOARD: float = Field(
        default=10.00,
        description="Cost in ZAR per bundled board generated (Directive 23)",
    )
    TOTAL_MONTHLY_BOARDS: int = Field(
        default=20,
        description="Default max boards per month (200 / 10 = 20) (Directive 23)",
    )
    BUDGET_CYCLE_ROLLOVER_DAY: int = Field(
        default=25,
        description="Day of month when budget cycle initializes (default 25th)",
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


settings = Settings()
