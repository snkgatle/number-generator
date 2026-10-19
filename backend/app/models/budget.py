"""MonthlyBudget model enforcing strict expenditure and board count limits."""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class MonthlyBudget(Base):
    """Enforces the monthly lottery budget and board limits.

    Directive 3 requires querying this table prior to board generation.
    If remaining_boards <= 0, execution is halted as 'Budget Exhausted'.
    """

    __tablename__ = "monthly_budgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    year_month: Mapped[str] = mapped_column(
        String(7),
        unique=True,
        index=True,
        nullable=False,
        comment="Formatted as YYYY-MM, e.g., 2026-10",
    )
    total_budget: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("200.00"),
    )
    cost_per_board: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("5.00"),
    )
    total_boards: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=40,
    )
    used_boards: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    remaining_boards: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=40,
    )
    spent_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    is_exhausted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    boards = relationship("GeneratedBoard", back_populates="budget", lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"<MonthlyBudget {self.year_month}: "
            f"{self.remaining_boards}/{self.total_boards} boards left "
            f"(exhausted={self.is_exhausted})>"
        )
