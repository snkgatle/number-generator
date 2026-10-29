"""Add generation_feedback table for outcome-calibrated generation.

Revision ID: 0008_generation_feedback
Revises: 0007_board_metrics_played
Create Date: 2026-10-29 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008_generation_feedback"
down_revision: Union[str, None] = "0007_board_metrics_played"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "generation_feedback",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("draw_id", sa.Integer(), nullable=False),
        sa.Column("bundle_name", sa.String(length=50), nullable=False),
        sa.Column("game_type", sa.String(length=50), nullable=False),
        sa.Column("draw_date", sa.Date(), nullable=False),
        sa.Column("boards_evaluated", sa.Integer(), nullable=False),
        sa.Column("accuracy_rate", sa.Float(), nullable=False),
        sa.Column("divergence_analysis", sa.Text(), nullable=True),
        sa.Column("calibration_recommendations", sa.JSON(), nullable=False),
        sa.Column("total_winnings", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("total_cost", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("roi_percentage", sa.Float(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["draw_id"], ["draws.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bundle_name", "draw_date", name="uq_feedback_bundle_date"),
    )
    op.create_index("ix_generation_feedback_draw_id", "generation_feedback", ["draw_id"])
    op.create_index("ix_generation_feedback_bundle_name", "generation_feedback", ["bundle_name"])
    op.create_index("ix_generation_feedback_draw_date", "generation_feedback", ["draw_date"])


def downgrade() -> None:
    op.drop_index("ix_generation_feedback_draw_date", table_name="generation_feedback")
    op.drop_index("ix_generation_feedback_bundle_name", table_name="generation_feedback")
    op.drop_index("ix_generation_feedback_draw_id", table_name="generation_feedback")
    op.drop_table("generation_feedback")
