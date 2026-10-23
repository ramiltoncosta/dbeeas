"""usuarios e tokens

Revision ID: 78a141a32420
Revises:
Create Date: 2026-10-23 08:08:47.438090
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "78a141a32420"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # PostGIS: usado a partir da etapa do mapa (pontos de coleta)
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "usuarios",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nome", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("senha_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "perfil",
            sa.Enum("pesquisador", "orgao_publico", "estudante", "admin", name="perfil"),
            nullable=False,
        ),
        sa.Column("instituicao", sa.String(length=200), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.Column("perfil_aprovado", sa.Boolean(), nullable=False),
        sa.Column("termos_aceitos_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consentimento_uso_fotos", sa.Boolean(), nullable=False),
        sa.Column("consentimento_uso_fotos_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ultimo_login_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_usuarios_email"), "usuarios", ["email"], unique=True)
    op.create_table(
        "tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("tipo", sa.Enum("refresh", "redefinir_senha", name="tipo_token"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(op.f("ix_tokens_usuario_id"), "tokens", ["usuario_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tokens_usuario_id"), table_name="tokens")
    op.drop_table("tokens")
    op.drop_index(op.f("ix_usuarios_email"), table_name="usuarios")
    op.drop_table("usuarios")
    sa.Enum(name="tipo_token").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="perfil").drop(op.get_bind(), checkfirst=True)
