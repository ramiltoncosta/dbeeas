"""Tabelas do banco de dados.

Etapa 1: usuários e tokens.
Etapa 2: espécies, modelos, coletas, fotos e identificações.
"""

import enum
import uuid
from datetime import date, datetime
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
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


# ---------------------------------------------------------------------------
# Etapa 2: espécies, modelos, coletas e fotos
# ---------------------------------------------------------------------------


class Especie(Base):
    """Espécies reconhecidas pelo modelo.

    São cadastradas automaticamente quando o modelo as identifica pela primeira vez.
    A ficha (descrição, características...) é preenchida pelo administrador na etapa 6.
    """

    __tablename__ = "especies"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome_cientifico: Mapped[str] = mapped_column(String(200), unique=True)
    # Espécie sensível: localização exata só para dono, pesquisador e administrador
    sensivel: Mapped[bool] = mapped_column(Boolean, default=False)
    raio_ofuscacao_km: Mapped[float] = mapped_column(Float, default=10.0)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ModeloIA(Base):
    """Versões do modelo YOLO que já fizeram identificações."""

    __tablename__ = "modelos"

    id: Mapped[int] = mapped_column(primary_key=True)
    versao: Mapped[str] = mapped_column(String(100), unique=True)
    especies: Mapped[list[str]] = mapped_column(JSONB, default=list)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Bioma(enum.StrEnum):
    amazonia = "amazonia"
    caatinga = "caatinga"
    cerrado = "cerrado"
    mata_atlantica = "mata_atlantica"
    pampa = "pampa"
    pantanal = "pantanal"


class Coleta(Base):
    """Uma amostra: as fotos de uma saída de campo."""

    __tablename__ = "coletas"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), index=True
    )
    nome: Mapped[str] = mapped_column(String(200))
    descricao: Mapped[str | None] = mapped_column(Text)
    data_coleta: Mapped[date | None] = mapped_column(Date)
    municipio: Mapped[str | None] = mapped_column(String(150))
    uf: Mapped[str | None] = mapped_column(String(2))
    coletor: Mapped[str | None] = mapped_column(String(200))
    tipo_armadilha: Mapped[str | None] = mapped_column(String(150))
    isca_atrativa: Mapped[str | None] = mapped_column(String(150))
    bioma: Mapped[Bioma | None] = mapped_column(_enum(Bioma, "bioma"))
    observacoes: Mapped[str | None] = mapped_column(Text)
    # Ponto geral da coleta. Fotos sem localização própria usam este ponto.
    local: Mapped[Any | None] = mapped_column(
        Geography("POINT", srid=4326, spatial_index=False)
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    fotos: Mapped[list["Foto"]] = relationship(
        back_populates="coleta", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (Index("ix_coletas_local", "local", postgresql_using="gist"),)


class StatusFoto(enum.StrEnum):
    na_fila = "na_fila"
    processando = "processando"
    concluida = "concluida"
    erro = "erro"


class OrigemLocal(enum.StrEnum):
    exif = "exif"  # veio dos metadados da foto (GPS da câmera/celular)
    manual = "manual"  # marcado pelo usuário no mapa


class Sexo(enum.StrEnum):
    femea = "femea"
    macho = "macho"
    indeterminado = "indeterminado"


class Foto(Base):
    __tablename__ = "fotos"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    coleta_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("coletas.id", ondelete="CASCADE"), index=True
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), index=True
    )

    # Arquivos (chaves no armazenamento)
    arquivo: Mapped[str] = mapped_column(String(300))
    miniatura: Mapped[str | None] = mapped_column(String(300))
    media: Mapped[str | None] = mapped_column(String(300))

    nome_original: Mapped[str] = mapped_column(String(255))
    tipo_mime: Mapped[str] = mapped_column(String(50))
    tamanho_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    largura: Mapped[int] = mapped_column(Integer)
    altura: Mapped[int] = mapped_column(Integer)

    data_captura: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    local: Mapped[Any | None] = mapped_column(Geography("POINT", srid=4326, spatial_index=False))
    origem_local: Mapped[OrigemLocal | None] = mapped_column(_enum(OrigemLocal, "origem_local"))
    sexo: Mapped[Sexo | None] = mapped_column(_enum(Sexo, "sexo"))

    status: Mapped[StatusFoto] = mapped_column(
        _enum(StatusFoto, "status_foto"), default=StatusFoto.na_fila, index=True
    )
    erro: Mapped[str | None] = mapped_column(Text)
    tentativas: Mapped[int] = mapped_column(Integer, default=0)
    enviada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    coleta: Mapped[Coleta] = relationship(back_populates="fotos")
    identificacoes: Mapped[list["Identificacao"]] = relationship(
        back_populates="foto",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Identificacao.criado_em.desc()",
    )

    __table_args__ = (
        # A mesma foto não entra duas vezes na mesma coleta
        UniqueConstraint("coleta_id", "sha256", name="uq_fotos_coleta_sha256"),
        Index("ix_fotos_local", "local", postgresql_using="gist"),
    )

    @property
    def identificacao(self) -> "Identificacao | None":
        """Resultado mais recente do modelo."""
        return self.identificacoes[0] if self.identificacoes else None


class Identificacao(Base):
    """Resultado do modelo para uma foto. Nunca é apagado nem alterado:
    as correções dos pesquisadores ficam em outra tabela (etapa 3)."""

    __tablename__ = "identificacoes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    foto_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("fotos.id", ondelete="CASCADE"), index=True
    )
    modelo_id: Mapped[int | None] = mapped_column(ForeignKey("modelos.id"))
    especie_id: Mapped[int | None] = mapped_column(ForeignKey("especies.id"), index=True)
    identificada: Mapped[bool] = mapped_column(Boolean)
    confianca: Mapped[float | None] = mapped_column(Float)
    deteccoes: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    foto: Mapped[Foto] = relationship(back_populates="identificacoes")
    especie: Mapped[Especie | None] = relationship()
    modelo: Mapped[ModeloIA | None] = relationship()
