"""exportacoes

Revision ID: d0d279fc4310
Revises: ad72f07e0c9c
Create Date: 2026-10-23 11:28:56.239502
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d0d279fc4310"
down_revision: str | None = "ad72f07e0c9c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "exportacoes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("coleta_id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column(
            "tipo_imagem",
            sa.Enum("original", "reduzida", name="tipo_imagem_exportacao"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("na_fila", "gerando", "pronta", "erro", name="status_exportacao"),
            nullable=False,
        ),
        sa.Column("arquivo", sa.String(length=300), nullable=True),
        sa.Column("tamanho_bytes", sa.BigInteger(), nullable=True),
        sa.Column("total_fotos", sa.Integer(), nullable=True),
        sa.Column("erro", sa.Text(), nullable=True),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("concluida_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["coleta_id"], ["coletas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_exportacoes_coleta_id"), "exportacoes", ["coleta_id"], unique=False)
    op.create_index(op.f("ix_exportacoes_usuario_id"), "exportacoes", ["usuario_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_exportacoes_usuario_id"), table_name="exportacoes")
    op.drop_index(op.f("ix_exportacoes_coleta_id"), table_name="exportacoes")
    op.drop_table("exportacoes")
    sa.Enum(name="status_exportacao").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="tipo_imagem_exportacao").drop(op.get_bind(), checkfirst=True)
