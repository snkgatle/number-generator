"""Make generated_boards.game_type nullable with default.

Revision ID: 0005_nullable_board_game_type
Revises: 0004_game_bundles
Create Date: 2026-10-22 11:47:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0005_nullable_board_game_type"
down_revision: Union[str, None] = "0004_game_bundles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "generated_boards",
        "game_type",
        nullable=True,
        server_default="",
    )


def downgrade() -> None:
    op.alter_column(
        "generated_boards",
        "game_type",
        nullable=False,
        server_default=None,
    )
