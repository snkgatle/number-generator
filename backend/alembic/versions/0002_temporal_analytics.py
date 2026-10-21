"""Add temporal_analytics table for weekly/monthly distributions and Qwen insights.

Revision ID: 0002_temporal_analytics
Revises: 0001_initial_schema
Create Date: 2026-10-21 04:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002_temporal_analytics"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "temporal_analytics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("game_type", sa.String(length=50), nullable=False),
        sa.Column("timeframe", sa.String(length=20), nullable=False),
        sa.Column("analysis_date", sa.Date(), nullable=False),
        sa.Column("sample_draws_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sum_average", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("sum_std_dev", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("parity_ratio", sa.String(length=20), nullable=False, server_default="3:3"),
        sa.Column("frequency_map", sa.JSON(), nullable=False),
        sa.Column("co_occurrence_matrix", sa.JSON(), nullable=False),
        sa.Column("actionable_bias_for_generation", sa.JSON(), nullable=True),
        sa.Column("ai_insights", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_temporal_analytics_game_type", "temporal_analytics", ["game_type"], unique=False)
    op.create_index("ix_temporal_analytics_timeframe", "temporal_analytics", ["timeframe"], unique=False)
    op.create_index("ix_temporal_analytics_analysis_date", "temporal_analytics", ["analysis_date"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_temporal_analytics_analysis_date", table_name="temporal_analytics")
    op.drop_index("ix_temporal_analytics_timeframe", table_name="temporal_analytics")
    op.drop_index("ix_temporal_analytics_game_type", table_name="temporal_analytics")
    op.drop_table("temporal_analytics")
