"""Tabelas do banco de dados.

Etapa 1: usuários e tokens. As demais tabelas (coletas, fotos, espécies,
planos...) entram nas próximas etapas.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Perfil(enum.StrEnum):
    pesquisador = "pesquisador"
    orgao_publico = "orgao_publico"
    estudante = "estudante"
    admin = "admin"


class TipoToken(enum.StrEnum):
    refresh = "refresh"  # mantém a sessão aberta
    redefinir_senha = "redefinir_senha"  # link do e-mail "esqueci minha senha"


def _enum(tipo, nome):
    # Guarda o valor do enum (ex.: "orgao_publico") como texto no banco
    return Enum(tipo, name=nome, values_callable=lambda e: [m.value for m in e])


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(String(255))
    perfil: Mapped[Perfil] = mapped_column(_enum(Perfil, "perfil"))
    instituicao: Mapped[str | None] = mapped_column(String(200))

    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    # Usado quando PESQUISADOR_REQUER_APROVACAO=true
    perfil_aprovado: Mapped[bool] = mapped_column(Boolean, default=True)

    # LGPD: quando aceitou os termos e se permitiu o uso das fotos para melhorar o modelo
    termos_aceitos_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consentimento_uso_fotos: Mapped[bool] = mapped_column(Boolean, default=False)
    consentimento_uso_fotos_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    ultimo_login_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tokens: Mapped[list["Token"]] = relationship(
        back_populates="usuario", cascade="all, delete-orphan", passive_deletes=True
    )


class Token(Base):
    """Tokens de sessão e de recuperação de senha.

    Guardamos só o hash: se alguém copiar o banco, não consegue usar os tokens.
    """

    __tablename__ = "tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), index=True
    )
    tipo: Mapped[TipoToken] = mapped_column(_enum(TipoToken, "tipo_token"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    usado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    usuario: Mapped[Usuario] = relationship(back_populates="tokens")
