"""TemporalAnalytics model storing weekly and monthly statistical aggregates, co-occurrence matrices, and Qwen pattern insights."""
from datetime import date, datetime
from typing import Any, Dict, Optional
from sqlalchemy import (
    Date,
    DateTime,
    Float,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class TemporalAnalytics(Base):
    """Stores temporal variance distributions and LLM pattern discovery insights.

    Directive 11: Calculates weekly (7-day) and monthly (30-day) statistical distributions.
    Uses PostgreSQL JSON to store co-occurrence matrices, frequency maps,
    and actionable bias to prevent passing raw historical arrays to Qwen.
    """

    __tablename__ = "temporal_analytics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="WEEKLY (7-day) or MONTHLY (30-day)",
    )
    analysis_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Date the analysis was conducted",
    )
    sample_draws_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Statistical aggregates (Directive 11)
    sum_average: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sum_std_dev: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    parity_ratio: Mapped[str] = mapped_column(String(20), nullable=False, default="3:3")

    # Co-occurrence matrices & frequency maps in JSON
    frequency_map: Mapped[Dict[str, int]] = mapped_column(JSON, nullable=False, default=dict)
    co_occurrence_matrix: Mapped[Dict[str, int]] = mapped_column(JSON, nullable=False, default=dict)

    # Actionable bias & AI insights
    actionable_bias_for_generation: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    ai_insights: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<TemporalAnalytics #{self.id} {self.game_type} [{self.timeframe}] "
            f"date={self.analysis_date} draws={self.sample_draws_count}>"
        )
