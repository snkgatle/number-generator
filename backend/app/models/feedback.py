"""Persisted post-draw performance feedback for outcome-calibrated generation."""
from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Optional

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class GenerationFeedback(Base, TimestampMixin):
    """Stores one Qwen post-draw review plus the realized bundle outcome.

    Feedback is keyed by bundle and draw date (Directive 24: a bundle night is
    evaluated across all its sub-draws at once), so repeated pipeline runs
    update the same row rather than duplicating history. ``draw_id`` stores a
    representative primary sub-draw for reference/joins. Only aggregate outcome
    data is persisted; raw historical draw arrays are never forwarded to the LLM.
    """

    __tablename__ = "generation_feedback"
    __table_args__ = (
        UniqueConstraint("bundle_name", "draw_date", name="uq_feedback_bundle_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    draw_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("draws.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Representative primary sub-draw for the bundle/date review",
    )
    bundle_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Bundle identifier: LOTTO_FAMILY, POWERBALL_FAMILY or DAILY_LOTTO",
    )
    game_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="",
        comment="Specific sub-draw game type that triggered the review",
    )
    draw_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    boards_evaluated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    accuracy_rate: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        comment="Qwen-reported alignment rate (0-1); diagnostic only, never used for allocation",
    )
    divergence_analysis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    calibration_recommendations: Mapped[List[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    total_winnings: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    total_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    roi_percentage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="qwen",
        comment="Feedback source: qwen, fallback, or manual",
    )

    def __repr__(self) -> str:
        return (
            f"<GenerationFeedback #{self.id} draw={self.draw_id} "
            f"bundle={self.bundle_name} accuracy={self.accuracy_rate:.2f} "
            f"roi={self.roi_percentage:.2f}%>"
        )
