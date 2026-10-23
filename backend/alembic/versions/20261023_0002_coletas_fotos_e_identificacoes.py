"""coletas fotos e identificacoes

Revision ID: f2c0cd1ca5b2
Revises: 78a141a32420
Create Date: 2026-10-23 08:54:38.775831
"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f2c0cd1ca5b2"
down_revision: str | None = "78a141a32420"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "especies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome_cientifico", sa.String(length=200), nullable=False),
        sa.Column("sensivel", sa.Boolean(), nullable=False),
        sa.Column("raio_ofuscacao_km", sa.Float(), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nome_cientifico"),
    )
    op.create_table(
        "modelos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("versao", sa.String(length=100), nullable=False),
        sa.Column("especies", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("versao"),
    )
    op.create_table(
        "coletas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("data_coleta", sa.Date(), nullable=True),
        sa.Column("municipio", sa.String(length=150), nullable=True),
        sa.Column("uf", sa.String(length=2), nullable=True),
        sa.Column("coletor", sa.String(length=200), nullable=True),
        sa.Column("tipo_armadilha", sa.String(length=150), nullable=True),
        sa.Column("isca_atrativa", sa.String(length=150), nullable=True),
        sa.Column(
            "bioma",
            sa.Enum(
                "amazonia",
                "caatinga",
                "cerrado",
                "mata_atlantica",
                "pampa",
                "pantanal",
                name="bioma",
            ),
            nullable=True,
        ),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column(
            "local",
            geoalchemy2.types.Geography(
                geometry_type="POINT",
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeogFromText",
                name="geography",
            ),
            nullable=True,
        ),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_coletas_local", "coletas", ["local"], unique=False, postgresql_using="gist")
    op.create_index(op.f("ix_coletas_usuario_id"), "coletas", ["usuario_id"], unique=False)
    op.create_table(
        "fotos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("coleta_id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("arquivo", sa.String(length=300), nullable=False),
        sa.Column("miniatura", sa.String(length=300), nullable=True),
        sa.Column("media", sa.String(length=300), nullable=True),
        sa.Column("nome_original", sa.String(length=255), nullable=False),
        sa.Column("tipo_mime", sa.String(length=50), nullable=False),
        sa.Column("tamanho_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("largura", sa.Integer(), nullable=False),
        sa.Column("altura", sa.Integer(), nullable=False),
        sa.Column("data_captura", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "local",
            geoalchemy2.types.Geography(
                geometry_type="POINT",
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeogFromText",
                name="geography",
            ),
            nullable=True,
        ),
        sa.Column("origem_local", sa.Enum("exif", "manual", name="origem_local"), nullable=True),
        sa.Column("sexo", sa.Enum("femea", "macho", "indeterminado", name="sexo"), nullable=True),
        sa.Column(
            "status",
            sa.Enum("na_fila", "processando", "concluida", "erro", name="status_foto"),
            nullable=False,
        ),
        sa.Column("erro", sa.Text(), nullable=True),
        sa.Column("tentativas", sa.Integer(), nullable=False),
        sa.Column(
            "enviada_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("processada_em", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["coleta_id"], ["coletas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("coleta_id", "sha256", name="uq_fotos_coleta_sha256"),
    )
    op.create_index(op.f("ix_fotos_coleta_id"), "fotos", ["coleta_id"], unique=False)
    op.create_index("ix_fotos_local", "fotos", ["local"], unique=False, postgresql_using="gist")
    op.create_index(op.f("ix_fotos_status"), "fotos", ["status"], unique=False)
    op.create_index(op.f("ix_fotos_usuario_id"), "fotos", ["usuario_id"], unique=False)
    op.create_table(
        "identificacoes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("foto_id", sa.Uuid(), nullable=False),
        sa.Column("modelo_id", sa.Integer(), nullable=True),
        sa.Column("especie_id", sa.Integer(), nullable=True),
        sa.Column("identificada", sa.Boolean(), nullable=False),
        sa.Column("confianca", sa.Float(), nullable=True),
        sa.Column("deteccoes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["especie_id"],
            ["especies.id"],
        ),
        sa.ForeignKeyConstraint(["foto_id"], ["fotos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["modelo_id"],
            ["modelos.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_identificacoes_especie_id"), "identificacoes", ["especie_id"], unique=False
    )
    op.create_index(op.f("ix_identificacoes_foto_id"), "identificacoes", ["foto_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_identificacoes_foto_id"), table_name="identificacoes")
    op.drop_index(op.f("ix_identificacoes_especie_id"), table_name="identificacoes")
    op.drop_table("identificacoes")
    op.drop_index(op.f("ix_fotos_usuario_id"), table_name="fotos")
    op.drop_index(op.f("ix_fotos_status"), table_name="fotos")
    op.drop_index("ix_fotos_local", table_name="fotos", postgresql_using="gist")
    op.drop_index(op.f("ix_fotos_coleta_id"), table_name="fotos")
    op.drop_table("fotos")
    op.drop_index(op.f("ix_coletas_usuario_id"), table_name="coletas")
    op.drop_index("ix_coletas_local", table_name="coletas", postgresql_using="gist")
    op.drop_table("coletas")
    op.drop_table("modelos")
    op.drop_table("especies")
    for nome in ("sexo", "origem_local", "status_foto", "bioma"):
        sa.Enum(name=nome).drop(op.get_bind(), checkfirst=True)
