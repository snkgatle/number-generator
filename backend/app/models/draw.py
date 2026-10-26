"""Draw model representing historical and scraped lottery draw results."""
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class Draw(Base):
    """Stores official historical lottery draw results.

    Directive 4 enforces unique constraint on (draw_number, game_type)
    to guarantee idempotent scraping.
    """

    __tablename__ = "draws"
    __table_args__ = (
        UniqueConstraint("draw_number", "game_type", name="uq_draw_number_game_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    draw_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    game_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    draw_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    numbers: Mapped[List[int]] = mapped_column(JSON, nullable=False)
    bonus_ball: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    powerball: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    machine_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    ball_set: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    draw_time: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    raw_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    bundle_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("game_bundles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    bundle = relationship("GameBundle", back_populates="draws", lazy="selectin")
    generated_boards = relationship("GeneratedBoard", back_populates="draw", lazy="selectin")
    results = relationship("BoardResult", back_populates="draw", cascade="all, delete-orphan", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Draw #{self.draw_number} - {self.game_type} ({self.draw_date})>"
