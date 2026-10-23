"""revisoes e especie final

Revision ID: ecdec8fe99af
Revises: f2c0cd1ca5b2
Create Date: 2026-10-23 10:02:56.902900
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "ecdec8fe99af"
down_revision: str | None = "f2c0cd1ca5b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "revisoes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("foto_id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=True),
        sa.Column(
            "perfil_revisor",
            # O tipo "perfil" já existe (tabela usuarios): não criar de novo
            postgresql.ENUM(name="perfil", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "acao",
            sa.Enum("confirmou", "corrigiu", "nao_identificavel", "restaurou", name="acao_revisao"),
            nullable=False,
        ),
        sa.Column("especie_id", sa.Integer(), nullable=True),
        sa.Column("identificacao_id", sa.Uuid(), nullable=True),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["especie_id"],
            ["especies.id"],
        ),
        sa.ForeignKeyConstraint(["foto_id"], ["fotos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["identificacao_id"], ["identificacoes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_revisoes_foto_id"), "revisoes", ["foto_id"], unique=False)
    op.create_index(op.f("ix_revisoes_usuario_id"), "revisoes", ["usuario_id"], unique=False)
    # Em add_column o tipo enum não é criado sozinho
    sa.Enum("modelo", "revisao", name="origem_especie").create(op.get_bind(), checkfirst=True)
    op.add_column("fotos", sa.Column("especie_id", sa.Integer(), nullable=True))
    op.add_column(
        "fotos",
        sa.Column(
            "origem_especie", sa.Enum("modelo", "revisao", name="origem_especie"), nullable=True
        ),
    )
    op.add_column(
        "fotos", sa.Column("revisada", sa.Boolean(), server_default="false", nullable=False)
    )
    op.create_index(op.f("ix_fotos_especie_id"), "fotos", ["especie_id"], unique=False)
    op.create_foreign_key("fk_fotos_especie_id", "fotos", "especies", ["especie_id"], ["id"])

    # Fotos já processadas: a espécie final é a do resultado mais recente do modelo
    op.execute(
        """
        UPDATE fotos f
        SET especie_id = ult.especie_id,
            origem_especie = CASE WHEN ult.especie_id IS NULL THEN NULL
                                  ELSE 'modelo' END::origem_especie
        FROM (
            SELECT DISTINCT ON (foto_id) foto_id, especie_id, identificada
            FROM identificacoes
            ORDER BY foto_id, criado_em DESC
        ) ult
        WHERE ult.foto_id = f.id AND ult.identificada
        """
    )


def downgrade() -> None:
    op.drop_constraint("fk_fotos_especie_id", "fotos", type_="foreignkey")
    op.drop_index(op.f("ix_fotos_especie_id"), table_name="fotos")
    op.drop_column("fotos", "revisada")
    op.drop_column("fotos", "origem_especie")
    op.drop_column("fotos", "especie_id")
    op.drop_index(op.f("ix_revisoes_usuario_id"), table_name="revisoes")
    op.drop_index(op.f("ix_revisoes_foto_id"), table_name="revisoes")
    op.drop_table("revisoes")
    sa.Enum(name="acao_revisao").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="origem_especie").drop(op.get_bind(), checkfirst=True)
