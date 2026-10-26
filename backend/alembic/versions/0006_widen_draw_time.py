"""Widen draw_time column from String(20) to String(50) to prevent overflow.

Revision ID: 0006_widen_draw_time
Revises: 0005_nullable_board_game_type
Create Date: 2026-10-26 09:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "0006_widen_draw_time"
down_revision: Union[str, None] = "0005_nullable_board_game_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "draws",
        "draw_time",
        existing_type=sa.String(20),
        type_=sa.String(50),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "draws",
        "draw_time",
        existing_type=sa.String(50),
        type_=sa.String(20),
        nullable=True,
    )