"""GameBundle model grouping sub-draws into unified playable bundles."""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import (
    DateTime,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class GameBundle(Base):
    """Represents a lottery game family bundle (Directive 21).

    Groups Lotto + Plus 1 + Plus 2 into LOTTO_FAMILY and
    PowerBall + PowerBall Plus into POWERBALL_FAMILY.
    A single generated board applies to all sub-draws in the bundle.
    """

    __tablename__ = "game_bundles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bundle_name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="'LOTTO_FAMILY' or 'POWERBALL_FAMILY'",
    )
    main_matrix_rule: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="'6/52' or '5/50'",
    )
    addon_matrix_rule: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="None for Lotto, '1/16' for PowerBall",
    )
    total_cost_per_board: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("10.00"),
        comment="True bundled cost, e.g., R10.00",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    draws = relationship("Draw", back_populates="bundle", lazy="selectin")
    generated_boards = relationship("GeneratedBoard", back_populates="bundle", lazy="selectin")

    def __repr__(self) -> str:
        return f"<GameBundle #{self.id} {self.bundle_name} cost=R{self.total_cost_per_board}>"
