"""Initial schema for draws, budgets, boards, and results.

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-10-18 08:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create draws table
    op.create_table(
        "draws",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("draw_number", sa.Integer(), nullable=False),
        sa.Column("game_type", sa.String(length=50), nullable=False),
        sa.Column("draw_date", sa.Date(), nullable=False),
        sa.Column("numbers", sa.JSON(), nullable=False),
        sa.Column("bonus_ball", sa.Integer(), nullable=True),
        sa.Column("powerball", sa.Integer(), nullable=True),
        sa.Column("raw_data", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("draw_number", "game_type", name="uq_draw_number_game_type"),
    )
    op.create_index("ix_draws_draw_number", "draws", ["draw_number"], unique=False)
    op.create_index("ix_draws_game_type", "draws", ["game_type"], unique=False)
    op.create_index("ix_draws_draw_date", "draws", ["draw_date"], unique=False)

    # 2. Create monthly_budgets table
    op.create_table(
        "monthly_budgets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("year_month", sa.String(length=7), nullable=False, comment="Formatted as YYYY-MM"),
        sa.Column("total_budget", sa.Numeric(precision=10, scale=2), nullable=False, server_default="200.00"),
        sa.Column("cost_per_board", sa.Numeric(precision=10, scale=2), nullable=False, server_default="5.00"),
        sa.Column("total_boards", sa.Integer(), nullable=False, server_default="40"),
        sa.Column("used_boards", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("remaining_boards", sa.Integer(), nullable=False, server_default="40"),
        sa.Column("spent_amount", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0.00"),
        sa.Column("is_exhausted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_monthly_budgets_year_month", "monthly_budgets", ["year_month"], unique=True)

    # 3. Create generated_boards table
    op.create_table(
        "generated_boards",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("budget_id", sa.Integer(), nullable=True),
        sa.Column("draw_id", sa.Integer(), nullable=True),
        sa.Column("game_type", sa.String(length=50), nullable=False),
        sa.Column("target_draw_date", sa.Date(), nullable=False),
        sa.Column("numbers", sa.JSON(), nullable=False),
        sa.Column("bonus_or_powerball", sa.Integer(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("ai_reasoning", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("cost", sa.Numeric(precision=10, scale=2), nullable=False, server_default="5.00"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["budget_id"], ["monthly_budgets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["draw_id"], ["draws.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_generated_boards_budget_id", "generated_boards", ["budget_id"], unique=False)
    op.create_index("ix_generated_boards_draw_id", "generated_boards", ["draw_id"], unique=False)
    op.create_index("ix_generated_boards_game_type", "generated_boards", ["game_type"], unique=False)
    op.create_index("ix_generated_boards_target_draw_date", "generated_boards", ["target_draw_date"], unique=False)
    op.create_index("ix_generated_boards_status", "generated_boards", ["status"], unique=False)

    # 4. Create board_results table
    op.create_table(
        "board_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("board_id", sa.Integer(), nullable=False),
        sa.Column("draw_id", sa.Integer(), nullable=False),
        sa.Column("matched_numbers", sa.JSON(), nullable=False),
        sa.Column("matched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("matched_bonus", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("division", sa.String(length=50), nullable=True),
        sa.Column("prize_amount", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0.00"),
        sa.Column(
            "evaluated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["board_id"], ["generated_boards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["draw_id"], ["draws.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_board_results_board_id", "board_results", ["board_id"], unique=True)
    op.create_index("ix_board_results_draw_id", "board_results", ["draw_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_board_results_draw_id", table_name="board_results")
    op.drop_index("ix_board_results_board_id", table_name="board_results")
    op.drop_table("board_results")

    op.drop_index("ix_generated_boards_status", table_name="generated_boards")
    op.drop_index("ix_generated_boards_target_draw_date", table_name="generated_boards")
    op.drop_index("ix_generated_boards_game_type", table_name="generated_boards")
    op.drop_index("ix_generated_boards_draw_id", table_name="generated_boards")
    op.drop_index("ix_generated_boards_budget_id", table_name="generated_boards")
    op.drop_table("generated_boards")

    op.drop_index("ix_monthly_budgets_year_month", table_name="monthly_budgets")
    op.drop_table("monthly_budgets")

    op.drop_index("ix_draws_draw_date", table_name="draws")
    op.drop_index("ix_draws_game_type", table_name="draws")
    op.drop_index("ix_draws_draw_number", table_name="draws")
    op.drop_table("draws")
