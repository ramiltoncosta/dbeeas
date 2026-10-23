"""planos, assinaturas e uso mensal

Cria os três planos iniciais, um período de teste para quem já tem conta
e o uso do mês atual a partir das fotos já enviadas.

Revision ID: fa0d335cd4de
Revises: 0daf27283797
Create Date: 2026-10-23 13:13:19.086872
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "fa0d335cd4de"
down_revision: str | None = "0daf27283797"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "planos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(length=40), nullable=False),
        sa.Column("nome", sa.String(length=80), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("preco_mensal_centavos", sa.Integer(), nullable=True),
        sa.Column("limite_fotos_mes", sa.Integer(), nullable=True),
        sa.Column("permite_exportacao", sa.Boolean(), nullable=False),
        sa.Column("publico", sa.Boolean(), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codigo"),
    )
    op.create_table(
        "assinaturas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("plano_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "teste", "pendente", "ativa", "suspensa", "cancelada", name="status_assinatura"
            ),
            nullable=False,
        ),
        sa.Column(
            "inicio", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("fim", sa.DateTime(timezone=True), nullable=True),
        sa.Column("origem", sa.String(length=40), nullable=False),
        sa.Column("codigo_externo", sa.String(length=120), nullable=True),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column("alterado_por_id", sa.Uuid(), nullable=True),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["alterado_por_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["plano_id"], ["planos.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_assinaturas_codigo_externo"), "assinaturas", ["codigo_externo"], unique=False
    )
    op.create_index(op.f("ix_assinaturas_criado_em"), "assinaturas", ["criado_em"], unique=False)
    op.create_index(op.f("ix_assinaturas_usuario_id"), "assinaturas", ["usuario_id"], unique=False)
    op.create_table(
        "uso_mensal",
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("mes", sa.Date(), nullable=False),
        sa.Column("fotos", sa.Integer(), nullable=False),
        sa.Column("identificacoes_rapidas", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("usuario_id", "mes"),
    )

    # Planos iniciais (preço vazio = a definir; o administrador ajusta pelo site)
    planos = sa.table(
        "planos",
        sa.column("codigo", sa.String),
        sa.column("nome", sa.String),
        sa.column("descricao", sa.Text),
        sa.column("limite_fotos_mes", sa.Integer),
        sa.column("permite_exportacao", sa.Boolean),
        sa.column("publico", sa.Boolean),
        sa.column("ordem", sa.Integer),
    )
    op.bulk_insert(
        planos,
        [
            {
                "codigo": "estudante",
                "nome": "Estudante",
                "descricao": "Para aprender e fazer trabalhos da graduação e da pós.",
                "limite_fotos_mes": 200,
                "permite_exportacao": True,
                "publico": True,
                "ordem": 1,
            },
            {
                "codigo": "pesquisador",
                "nome": "Pesquisador",
                "descricao": "Para quem processa coletas de campo com frequência.",
                "limite_fotos_mes": 2000,
                "permite_exportacao": True,
                "publico": True,
                "ordem": 2,
            },
            {
                "codigo": "institucional",
                "nome": "Institucional",
                "descricao": "Para órgãos públicos, universidades e laboratórios.",
                "limite_fotos_mes": 10000,
                "permite_exportacao": True,
                "publico": True,
                "ordem": 3,
            },
        ],
    )

    # Quem já tem conta ganha 30 dias de teste no plano do seu perfil
    op.execute(
        """
        INSERT INTO assinaturas (id, usuario_id, plano_id, status, fim, origem, observacao)
        SELECT gen_random_uuid(), u.id, p.id, 'teste', now() + interval '30 days', 'manual',
               'Período de teste criado na atualização do sistema'
        FROM usuarios u
        JOIN planos p ON p.codigo = CASE u.perfil
            WHEN 'estudante' THEN 'estudante'
            WHEN 'orgao_publico' THEN 'institucional'
            ELSE 'pesquisador' END
        WHERE u.perfil <> 'admin'
        """
    )

    # Uso do mês atual a partir das fotos já enviadas
    op.execute(
        """
        INSERT INTO uso_mensal (usuario_id, mes, fotos, identificacoes_rapidas)
        SELECT usuario_id, date_trunc('month', now() AT TIME ZONE 'America/Sao_Paulo')::date,
               count(*), 0
        FROM fotos
        WHERE enviada_em >= date_trunc('month', now() AT TIME ZONE 'America/Sao_Paulo')
                            AT TIME ZONE 'America/Sao_Paulo'
        GROUP BY usuario_id
        """
    )


def downgrade() -> None:
    op.drop_table("uso_mensal")
    op.drop_index(op.f("ix_assinaturas_usuario_id"), table_name="assinaturas")
    op.drop_index(op.f("ix_assinaturas_criado_em"), table_name="assinaturas")
    op.drop_index(op.f("ix_assinaturas_codigo_externo"), table_name="assinaturas")
    op.drop_table("assinaturas")
    op.drop_table("planos")
    sa.Enum(name="status_assinatura").drop(op.get_bind(), checkfirst=True)
