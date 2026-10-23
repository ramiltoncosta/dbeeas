"""coleta publica no mapa

Revision ID: ad72f07e0c9c
Revises: ecdec8fe99af
Create Date: 2026-10-23 10:40:04.780340
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "ad72f07e0c9c"
down_revision: str | None = "ecdec8fe99af"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "coletas", sa.Column("publica_no_mapa", sa.Boolean(), server_default="true", nullable=False)
    )


def downgrade() -> None:
    op.drop_column("coletas", "publica_no_mapa")
