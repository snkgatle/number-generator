"""Add game_bundles table, map draws and generated_boards to bundles.

Revision ID: 0004_game_bundles
Revises: 0003_draw_metadata
Create Date: 2026-10-22 10:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column

# revision identifiers, used by Alembic.
revision: str = "0004_game_bundles"
down_revision: Union[str, None] = "0003_draw_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create game_bundles table
    op.create_table(
        "game_bundles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("bundle_name", sa.String(length=50), nullable=False),
        sa.Column("main_matrix_rule", sa.String(length=20), nullable=False),
        sa.Column("addon_matrix_rule", sa.String(length=20), nullable=True),
        sa.Column("total_cost_per_board", sa.Numeric(precision=5, scale=2), nullable=False, server_default="10.00"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bundle_name"),
    )
    op.create_index("ix_game_bundles_bundle_name", "game_bundles", ["bundle_name"], unique=True)

    # 2. Seed initial game bundles (LOTTO_FAMILY and POWERBALL_FAMILY)
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
                "bundle_name": "LOTTO_FAMILY",
                "main_matrix_rule": "6/52",
                "addon_matrix_rule": None,
                "total_cost_per_board": 10.00,
            },
            {
                "bundle_name": "POWERBALL_FAMILY",
                "main_matrix_rule": "5/50",
                "addon_matrix_rule": "1/16",
                "total_cost_per_board": 10.00,
            },
        ],
    )

    # 3. Add bundle_id to draws and backfill
    op.add_column("draws", sa.Column("bundle_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_draws_bundle_id_game_bundles",
        "draws",
        "game_bundles",
        ["bundle_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_draws_bundle_id", "draws", ["bundle_id"], unique=False)

    op.execute(
        """
        UPDATE draws 
        SET bundle_id = (SELECT id FROM game_bundles WHERE bundle_name = 'LOTTO_FAMILY')
        WHERE game_type IN ('LOTTO', 'LOTTO_PLUS_1', 'LOTTO_PLUS_2');
        """
    )
    op.execute(
        """
        UPDATE draws 
        SET bundle_id = (SELECT id FROM game_bundles WHERE bundle_name = 'POWERBALL_FAMILY')
        WHERE game_type IN ('POWERBALL', 'POWERBALL_PLUS');
        """
    )

    # 4. Add bundle_id and bundle_name to generated_boards
    op.add_column("generated_boards", sa.Column("bundle_id", sa.Integer(), nullable=True))
    op.add_column("generated_boards", sa.Column("bundle_name", sa.String(length=50), nullable=True))
    op.create_foreign_key(
        "fk_generated_boards_bundle_id_game_bundles",
        "generated_boards",
        "game_bundles",
        ["bundle_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_generated_boards_bundle_id", "generated_boards", ["bundle_id"], unique=False)

    op.execute(
        """
        UPDATE generated_boards
        SET bundle_name = CASE 
            WHEN game_type LIKE 'POWERBALL%' THEN 'POWERBALL_FAMILY'
            ELSE 'LOTTO_FAMILY'
        END;
        """
    )
    op.execute(
        """
        UPDATE generated_boards
        SET bundle_id = (SELECT id FROM game_bundles WHERE bundle_name = generated_boards.bundle_name);
        """
    )
    op.alter_column("generated_boards", "bundle_name", nullable=False)
    op.create_index("ix_generated_boards_bundle_name", "generated_boards", ["bundle_name"], unique=False)

    # 5. Update board_results: add game_type, drop unique index on board_id, create non-unique index and composite constraint
    op.add_column("board_results", sa.Column("game_type", sa.String(length=50), nullable=False, server_default=""))
    op.create_index("ix_board_results_game_type", "board_results", ["game_type"], unique=False)

    op.execute(
        """
        UPDATE board_results 
        SET game_type = COALESCE((SELECT game_type FROM draws WHERE draws.id = board_results.draw_id), '');
        """
    )

    op.execute("DROP INDEX IF EXISTS ix_board_results_board_id;")
    op.create_index("ix_board_results_board_id", "board_results", ["board_id"], unique=False)
    op.create_unique_constraint("uq_board_draw_result", "board_results", ["board_id", "draw_id"])


def downgrade() -> None:
    op.drop_constraint("uq_board_draw_result", "board_results", type_="unique")
    op.drop_index("ix_board_results_game_type", table_name="board_results")
    op.drop_column("board_results", "game_type")

    op.drop_index("ix_board_results_board_id", table_name="board_results")
    op.create_index("ix_board_results_board_id", "board_results", ["board_id"], unique=True)

    op.drop_index("ix_generated_boards_bundle_name", table_name="generated_boards")
    op.drop_index("ix_generated_boards_bundle_id", table_name="generated_boards")
    op.drop_constraint("fk_generated_boards_bundle_id_game_bundles", "generated_boards", type_="foreignkey")
    op.drop_column("generated_boards", "bundle_name")
    op.drop_column("generated_boards", "bundle_id")

    op.drop_index("ix_draws_bundle_id", table_name="draws")
    op.drop_constraint("fk_draws_bundle_id_game_bundles", "draws", type_="foreignkey")
    op.drop_column("draws", "bundle_id")

    op.drop_index("ix_game_bundles_bundle_name", table_name="game_bundles")
    op.drop_table("game_bundles")
