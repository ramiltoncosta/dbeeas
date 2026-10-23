"""Tabelas do banco de dados.

Etapa 1: usuários e tokens.
Etapa 2: espécies, modelos, coletas, fotos e identificações.
Etapa 3: revisões. Etapa 5: exportações. Etapa 6: fichas e mensagens de contato.
Etapa 7: planos, assinaturas e uso mensal.
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
    A ficha (descrição, características...) fica em FichaEspecie.
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
    # Se True, as ocorrências desta coleta aparecem no mapa geral da plataforma
    # (sem fotos nem nome da coleta, e com localização aproximada para espécies sensíveis)
    publica_no_mapa: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # Ponto geral da coleta. Fotos sem localização própria usam este ponto.
    local: Mapped[Any | None] = mapped_column(Geography("POINT", srid=4326, spatial_index=False))
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


class OrigemEspecie(enum.StrEnum):
    modelo = "modelo"  # resultado do modelo
    revisao = "revisao"  # confirmada ou corrigida por uma pessoa


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

    # Espécie final da foto: a da revisão mais recente, se houver; senão, a do modelo.
    # Fica guardada aqui (calculada) para o gráfico, o mapa e a exportação serem rápidos.
    especie_id: Mapped[int | None] = mapped_column(ForeignKey("especies.id"), index=True)
    origem_especie: Mapped[OrigemEspecie | None] = mapped_column(
        _enum(OrigemEspecie, "origem_especie")
    )
    revisada: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    coleta: Mapped[Coleta] = relationship(back_populates="fotos")
    especie: Mapped[Especie | None] = relationship()
    revisoes: Mapped[list["Revisao"]] = relationship(
        back_populates="foto",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Revisao.criado_em.desc()",
    )
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

    @property
    def revisao(self) -> "Revisao | None":
        """Revisão mais recente feita por uma pessoa."""
        return self.revisoes[0] if self.revisoes else None


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


class AcaoRevisao(enum.StrEnum):
    confirmou = "confirmou"  # a espécie do modelo está certa
    corrigiu = "corrigiu"  # a espécie certa é outra
    nao_identificavel = "nao_identificavel"  # não dá para identificar por esta foto
    restaurou = "restaurou"  # desfez as revisões: volta a valer o resultado do modelo


class Revisao(Base):
    """Confirmações e correções feitas por pessoas. Nunca são apagadas:
    formam o histórico e servem de dado para retreinar o modelo."""

    __tablename__ = "revisoes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    foto_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("fotos.id", ondelete="CASCADE"), index=True
    )
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), index=True
    )
    # Perfil de quem revisou, no momento da revisão (para filtrar no retreino)
    perfil_revisor: Mapped[Perfil] = mapped_column(_enum(Perfil, "perfil"))
    acao: Mapped[AcaoRevisao] = mapped_column(_enum(AcaoRevisao, "acao_revisao"))
    especie_id: Mapped[int | None] = mapped_column(ForeignKey("especies.id"))
    # O que o modelo dizia quando a revisão foi feita
    identificacao_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("identificacoes.id", ondelete="SET NULL")
    )
    observacao: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    foto: Mapped[Foto] = relationship(back_populates="revisoes")
    especie: Mapped[Especie | None] = relationship()
    usuario: Mapped[Usuario | None] = relationship()


# ---------------------------------------------------------------------------
# Etapa 5: exportação da coleta (amostra digital)
# ---------------------------------------------------------------------------


class StatusExportacao(enum.StrEnum):
    na_fila = "na_fila"
    gerando = "gerando"
    pronta = "pronta"
    erro = "erro"


class TipoImagemExportacao(enum.StrEnum):
    original = "original"  # arquivo enviado, sem alteração
    reduzida = "reduzida"  # versão de até 1600 px (arquivo bem menor)


class Exportacao(Base):
    """Arquivo ZIP com as fotos separadas por espécie e a planilha Darwin Core."""

    __tablename__ = "exportacoes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    coleta_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("coletas.id", ondelete="CASCADE"), index=True
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), index=True
    )
    tipo_imagem: Mapped[TipoImagemExportacao] = mapped_column(
        _enum(TipoImagemExportacao, "tipo_imagem_exportacao")
    )
    status: Mapped[StatusExportacao] = mapped_column(
        _enum(StatusExportacao, "status_exportacao"), default=StatusExportacao.na_fila
    )
    arquivo: Mapped[str | None] = mapped_column(String(300))
    tamanho_bytes: Mapped[int | None] = mapped_column(BigInteger)
    total_fotos: Mapped[int | None] = mapped_column(Integer)
    erro: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    concluida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expira_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# --- Etapa 6: fichas das espécies e mensagens de contato ------------------------


class FichaEspecie(Base):
    """Ficha de uma espécie (base para estudantes), escrita por especialistas.

    O texto fica no banco (não no código) para o administrador editar pelo site.
    Só aparece para o público depois de publicada.
    """

    __tablename__ = "fichas_especies"

    especie_id: Mapped[int] = mapped_column(
        ForeignKey("especies.id", ondelete="CASCADE"), primary_key=True
    )
    nome_popular: Mapped[str | None] = mapped_column(String(200))
    autoria: Mapped[str | None] = mapped_column(String(200))  # ex.: "Moure, 1970"
    descricao: Mapped[str | None] = mapped_column(Text)
    caracteristicas: Mapped[str | None] = mapped_column(Text)
    distribuicao: Mapped[str | None] = mapped_column(Text)
    fontes: Mapped[str | None] = mapped_column(Text)  # uma referência por linha
    imagem: Mapped[str | None] = mapped_column(String(300))
    credito_imagem: Mapped[str | None] = mapped_column(String(300))
    publicada: Mapped[bool] = mapped_column(Boolean, default=False)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    atualizado_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL")
    )

    especie: Mapped[Especie] = relationship()
    atualizado_por: Mapped[Usuario | None] = relationship()


class MensagemContato(Base):
    """Mensagens do formulário de contato da página pública.

    Ficam guardadas além de irem por e-mail: nada se perde se o e-mail falhar.
    """

    __tablename__ = "mensagens_contato"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254))
    instituicao: Mapped[str | None] = mapped_column(String(200))
    assunto: Mapped[str] = mapped_column(String(40))
    mensagem: Mapped[str] = mapped_column(Text)
    respondida: Mapped[bool] = mapped_column(Boolean, default=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


# --- Etapa 7: planos, assinaturas e uso -------------------------------------------


class Plano(Base):
    """Plano de assinatura. Valores e limites são editados pelo administrador."""

    __tablename__ = "planos"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(40), unique=True)  # ex.: "pesquisador"
    nome: Mapped[str] = mapped_column(String(80))
    descricao: Mapped[str | None] = mapped_column(Text)
    # Preço por mês em centavos (evita erros de arredondamento). Vazio = "sob consulta".
    preco_mensal_centavos: Mapped[int | None] = mapped_column(Integer)
    # Fotos por mês (coletas + identificação rápida). Vazio = sem limite.
    limite_fotos_mes: Mapped[int | None] = mapped_column(Integer)
    permite_exportacao: Mapped[bool] = mapped_column(Boolean, default=True)
    # Aparece na página pública e pode ser pedido pelos usuários
    publico: Mapped[bool] = mapped_column(Boolean, default=True)
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StatusAssinatura(enum.StrEnum):
    teste = "teste"  # período de teste gratuito
    pendente = "pendente"  # pedida, aguardando pagamento ou ativação
    ativa = "ativa"
    suspensa = "suspensa"  # ex.: pagamento atrasado
    cancelada = "cancelada"


class Assinatura(Base):
    """Histórico de assinaturas. A atual é a mais recente do usuário.

    Nunca é apagada: cada mudança cria uma linha nova (dá para ver o histórico).
    """

    __tablename__ = "assinaturas"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), index=True
    )
    plano_id: Mapped[int] = mapped_column(ForeignKey("planos.id", ondelete="RESTRICT"))
    status: Mapped[StatusAssinatura] = mapped_column(_enum(StatusAssinatura, "status_assinatura"))
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Até quando vale. Vazio = sem prazo.
    fim: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # "manual" (administrador) ou o nome do serviço de pagamento
    origem: Mapped[str] = mapped_column(String(40), default="manual")
    codigo_externo: Mapped[str | None] = mapped_column(String(120), index=True)
    observacao: Mapped[str | None] = mapped_column(Text)
    alterado_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL")
    )
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    plano: Mapped[Plano] = relationship()
    alterado_por: Mapped[Usuario | None] = relationship(foreign_keys=[alterado_por_id])


class UsoMensal(Base):
    """Quantas fotos cada usuário enviou no mês (para o limite do plano).

    É um contador: apagar fotos não devolve o saldo do mês.
    """

    __tablename__ = "uso_mensal"

    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True
    )
    mes: Mapped[date] = mapped_column(Date, primary_key=True)  # sempre o dia 1
    fotos: Mapped[int] = mapped_column(Integer, default=0)
    identificacoes_rapidas: Mapped[int] = mapped_column(Integer, default=0)


class FotoJaContada(Base):
    """Fotos da identificação rápida que já entraram no limite do mês.

    Se a pessoa salvar essas mesmas fotos numa coleta, elas não contam de novo.
    """

    __tablename__ = "fotos_ja_contadas"

    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True
    )
    sha256: Mapped[str] = mapped_column(String(64), primary_key=True)
    mes: Mapped[date] = mapped_column(Date, index=True)
