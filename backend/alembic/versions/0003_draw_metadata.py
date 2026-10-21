"""Add machine_name, ball_set, and draw_time columns to draws table.

Revision ID: 0003_draw_metadata
Revises: 0002_temporal_analytics
Create Date: 2026-10-21 04:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003_draw_metadata"
down_revision: Union[str, None] = "0002_temporal_analytics"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("draws", sa.Column("machine_name", sa.String(length=50), nullable=True))
    op.add_column("draws", sa.Column("ball_set", sa.String(length=50), nullable=True))
    op.add_column("draws", sa.Column("draw_time", sa.String(length=20), nullable=True))
    op.create_index("ix_draws_machine_name", "draws", ["machine_name"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_draws_machine_name", table_name="draws")
    op.drop_column("draws", "draw_time")
    op.drop_column("draws", "ball_set")
    op.drop_column("draws", "machine_name")
