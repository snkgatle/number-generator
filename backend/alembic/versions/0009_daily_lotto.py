"""Add budget pools and seed the DAILY_LOTTO game bundle.

Revision ID: 0009_daily_lotto
Revises: 0008_generation_feedback
Create Date: 2026-10-29 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column


revision: str = "0009_daily_lotto"
down_revision: Union[str, None] = "0008_generation_feedback"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add a budget pool discriminator so bundle and Daily Lotto quotas are isolated.
    op.add_column(
        "monthly_budgets",
        sa.Column(
            "pool",
            sa.String(length=30),
            nullable=False,
            server_default="BUNDLE",
            comment="Budget pool: 'BUNDLE' or 'DAILY_LOTTO'",
        ),
    )
    op.execute("UPDATE monthly_budgets SET pool = 'BUNDLE';")

    # 2. Replace the single-period uniqueness with per-(period, pool) uniqueness.
    op.drop_index("ix_monthly_budgets_year_month", table_name="monthly_budgets")
    op.create_unique_constraint(
        "uq_monthly_budget_period_pool",
        "monthly_budgets",
        ["year_month", "pool"],
    )
    op.create_index(
        "ix_monthly_budgets_pool", "monthly_budgets", ["pool"], unique=False
    )

    # 3. Seed the Daily Lotto single-member bundle (5/36, R3.00 per board).
    bundles_table = table(
        "game_bundles",
        column("bundle_name", sa.String),
        column("main_matrix_rule", sa.String),
        column("addon_matrix_rule", sa.String),
        column("total_cost_per_board", sa.Numeric),
    )
    op.bulk_insert(
        bundles_table,
        [
            {
                "bundle_name": "DAILY_LOTTO",
                "main_matrix_rule": "5/36",
                "addon_matrix_rule": None,
                "total_cost_per_board": 3.00,
            },
        ],
    )


def downgrade() -> None:
    op.execute("DELETE FROM game_bundles WHERE bundle_name = 'DAILY_LOTTO';")
    op.drop_index("ix_monthly_budgets_pool", table_name="monthly_budgets")
    op.drop_constraint(
        "uq_monthly_budget_period_pool", "monthly_budgets", type_="unique"
    )
    op.create_index(
        "ix_monthly_budgets_year_month", "monthly_budgets", ["year_month"], unique=True
    )
    op.drop_column("monthly_budgets", "pool")
