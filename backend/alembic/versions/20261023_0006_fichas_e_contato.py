"""fichas das espécies e mensagens de contato

Revision ID: 0daf27283797
Revises: d0d279fc4310
Create Date: 2026-10-23 11:45:07.526423
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0daf27283797"
down_revision: str | None = "d0d279fc4310"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mensagens_contato",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("instituicao", sa.String(length=200), nullable=True),
        sa.Column("assunto", sa.String(length=40), nullable=False),
        sa.Column("mensagem", sa.Text(), nullable=False),
        sa.Column("respondida", sa.Boolean(), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mensagens_contato_criado_em"), "mensagens_contato", ["criado_em"], unique=False
    )
    op.create_table(
        "fichas_especies",
        sa.Column("especie_id", sa.Integer(), nullable=False),
        sa.Column("nome_popular", sa.String(length=200), nullable=True),
        sa.Column("autoria", sa.String(length=200), nullable=True),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("caracteristicas", sa.Text(), nullable=True),
        sa.Column("distribuicao", sa.Text(), nullable=True),
        sa.Column("fontes", sa.Text(), nullable=True),
        sa.Column("imagem", sa.String(length=300), nullable=True),
        sa.Column("credito_imagem", sa.String(length=300), nullable=True),
        sa.Column("publicada", sa.Boolean(), nullable=False),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("atualizado_por_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["atualizado_por_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["especie_id"], ["especies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("especie_id"),
    )


def downgrade() -> None:
    op.drop_table("fichas_especies")
    op.drop_index(op.f("ix_mensagens_contato_criado_em"), table_name="mensagens_contato")
    op.drop_table("mensagens_contato")
