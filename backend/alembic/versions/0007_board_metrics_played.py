"""Add simulated_hit_rate, ev_score, and played_at to generated_boards.

Revision ID: 0007_board_metrics_played
Revises: 0006_widen_draw_time
Create Date: 2026-10-26 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "0007_board_metrics_played"
down_revision: Union[str, None] = "0006_widen_draw_time"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "generated_boards",
        sa.Column("simulated_hit_rate", sa.Float(), nullable=True),
    )
    op.add_column(
        "generated_boards",
        sa.Column("ev_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "generated_boards",
        sa.Column("played_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("generated_boards", "played_at")
    op.drop_column("generated_boards", "ev_score")
    op.drop_column("generated_boards", "simulated_hit_rate")
