"""GeneratedBoard and BoardResult models for tracking generated tickets and outcomes."""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import (
    Boolean,
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
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class GeneratedBoard(Base):
    """Represents a set of lottery numbers generated for a Game Bundle.

    Directive 21: One generated board applies to all sub-draws within that bundle
    (e.g., LOTTO_FAMILY applies to Lotto, Plus 1, Plus 2; POWERBALL_FAMILY
    applies to PowerBall and PowerBall Plus; DAILY_LOTTO is standalone).
    """

    __tablename__ = "generated_boards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bundle_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("game_bundles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    budget_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("monthly_budgets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    draw_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("draws.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    bundle_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Bundle identifier: 'LOTTO_FAMILY', 'POWERBALL_FAMILY' or 'DAILY_LOTTO'",
    )
    game_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        default="",
        index=True,
        comment="Legacy game_type column, mapped to bundle_name for backward compatibility",
    )
    target_draw_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    numbers: Mapped[List[int]] = mapped_column(JSON, nullable=False)
    bonus_or_powerball: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="AI confidence percentage between 0.0 and 100.0",
    )
    ai_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PENDING",
        index=True,
        comment="Status: PENDING, PLAYED, WON, LOST, VOID",
    )
    simulated_hit_rate: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Directive 15: Monte Carlo simulated hit rate (0.0-1.0) from 10k iterations",
    )
    ev_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Directive 20: Expected Value score (0-100) penalizing human-biased combinations",
    )
    played_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Directive 10: timestamp when user manually played this board on the official platform",
    )
    cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("10.00"),
        comment="True bundle cost (R10.00)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    bundle = relationship("GameBundle", back_populates="generated_boards", lazy="selectin")
    budget = relationship("MonthlyBudget", back_populates="boards", lazy="selectin")
    draw = relationship("Draw", back_populates="generated_boards", lazy="selectin")
    results = relationship(
        "BoardResult",
        back_populates="board",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


    def __init__(self, **kwargs):
        if "bundle_name" in kwargs and "game_type" not in kwargs:
            kwargs["game_type"] = kwargs["bundle_name"]
        elif "game_type" in kwargs and "bundle_name" not in kwargs:
            kwargs["bundle_name"] = kwargs["game_type"]
        elif "bundle_name" not in kwargs and "game_type" not in kwargs:
            raise ValueError(
                "GeneratedBoard requires either 'bundle_name' or 'game_type'; "
                "refusing to silently default to LOTTO_FAMILY."
            )
        super().__init__(**kwargs)

    @property
    def result(self) -> Optional["BoardResult"]:
        """Backward compatibility property returning primary/first result."""
        return self.results[0] if self.results else None

    @property
    def total_prize(self) -> Decimal:
        """Directive 24: Sum the prizes across all sub-draw results for this board."""
        return sum((r.prize_amount for r in self.results), Decimal("0.00"))

    def __repr__(self) -> str:
        return (
            f"<GeneratedBoard #{self.id} {self.bundle_name} "
            f"target={self.target_draw_date} conf={self.confidence_score}% status={self.status}>"
        )


class BoardResult(Base):
    """Post-draw evaluation results comparing a generated board against official draw outcomes.

    Directive 24: A single generated board has multiple results (one for each sub-draw in the bundle).
    """

    __tablename__ = "board_results"
    __table_args__ = (
        UniqueConstraint("board_id", "draw_id", name="uq_board_draw_result"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    board_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("generated_boards.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    draw_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("draws.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    game_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="",
        index=True,
        comment="Specific sub-draw (e.g., LOTTO, LOTTO_PLUS_1, POWERBALL, POWERBALL_PLUS)",
    )
    matched_numbers: Mapped[List[int]] = mapped_column(JSON, nullable=False, default=list)
    matched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    matched_bonus: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    division: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    prize_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    board = relationship("GeneratedBoard", back_populates="results", lazy="selectin")
    draw = relationship("Draw", back_populates="results", lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"<BoardResult board_id={self.board_id} game={self.game_type} "
            f"matched={self.matched_count} prize=R{self.prize_amount}>"
        )
