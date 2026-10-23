"""Formatos de entrada e saída de coletas e fotos."""

import re
import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.armazenamento import url_assinada
from app.geo import lat_lon
from app.models import (
    AcaoRevisao,
    Bioma,
    Coleta,
    Foto,
    OrigemEspecie,
    OrigemLocal,
    Perfil,
    Sexo,
    StatusFoto,
)

UFS = {
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA",
    "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
}  # fmt: skip


class Ponto(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


def _texto(v):
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


class _CamposColeta(BaseModel):
    descricao: str | None = Field(default=None, max_length=5000)
    data_coleta: date | None = None
    municipio: str | None = Field(default=None, max_length=150)
    uf: str | None = None
    coletor: str | None = Field(default=None, max_length=200)
    tipo_armadilha: str | None = Field(default=None, max_length=150)
    isca_atrativa: str | None = Field(default=None, max_length=150)
    bioma: Bioma | None = None
    observacoes: str | None = Field(default=None, max_length=5000)
    local: Ponto | None = None
    publica_no_mapa: bool = True

    @field_validator(
        "descricao", "municipio", "coletor", "tipo_armadilha", "isca_atrativa", "observacoes",
        mode="before",
    )  # fmt: skip
    @classmethod
    def _limpar(cls, v):
        return _texto(v)

    @field_validator("uf", mode="before")
    @classmethod
    def _uf(cls, v):
        v = _texto(v)
        if v is None:
            return None
        v = v.upper()
        if v not in UFS:
            raise ValueError("UF inválida")
        return v

    @field_validator("data_coleta")
    @classmethod
    def _data(cls, v):
        if v and v > date.today():
            raise ValueError("A data da coleta não pode estar no futuro")
        return v


class ColetaIn(_CamposColeta):
    nome: str = Field(min_length=1, max_length=200)

    @field_validator("nome", mode="before")
    @classmethod
    def _nome(cls, v):
        return v.strip() if isinstance(v, str) else v


class ColetaAtualizar(_CamposColeta):
    """Só os campos enviados são alterados. Envie null para apagar um campo."""

    nome: str | None = Field(default=None, min_length=1, max_length=200)


class Contagem(BaseModel):
    total: int = 0
    na_fila: int = 0
    processando: int = 0
    concluidas: int = 0
    erro: int = 0
    identificadas: int = 0
    nao_identificadas: int = 0


class ColetaOut(BaseModel):
    id: uuid.UUID
    usuario_id: uuid.UUID
    nome: str
    descricao: str | None
    data_coleta: date | None
    municipio: str | None
    uf: str | None
    coletor: str | None
    tipo_armadilha: str | None
    isca_atrativa: str | None
    bioma: Bioma | None
    observacoes: str | None
    local: Ponto | None
    publica_no_mapa: bool
    criado_em: datetime
    atualizado_em: datetime
    fotos: Contagem = Contagem()

    @classmethod
    def de(cls, c: Coleta, contagem: Contagem | None = None) -> "ColetaOut":
        lat, lon = lat_lon(c.local)
        return cls(
            id=c.id,
            usuario_id=c.usuario_id,
            nome=c.nome,
            descricao=c.descricao,
            data_coleta=c.data_coleta,
            municipio=c.municipio,
            uf=c.uf,
            coletor=c.coletor,
            tipo_armadilha=c.tipo_armadilha,
            isca_atrativa=c.isca_atrativa,
            bioma=c.bioma,
            observacoes=c.observacoes,
            local=Ponto(latitude=lat, longitude=lon) if lat is not None else None,
            publica_no_mapa=c.publica_no_mapa,
            criado_em=c.criado_em,
            atualizado_em=c.atualizado_em,
            fotos=contagem or Contagem(),
        )


class IdentificacaoOut(BaseModel):
    identificada: bool
    especie: str | None
    confianca: float | None
    deteccoes: list[dict]
    versao_modelo: str | None
    criado_em: datetime


class RevisaoOut(BaseModel):
    acao: AcaoRevisao
    especie: str | None
    observacao: str | None
    revisor: str | None
    perfil_revisor: Perfil
    criado_em: datetime


class FotoOut(BaseModel):
    id: uuid.UUID
    coleta_id: uuid.UUID
    nome_original: str
    largura: int
    altura: int
    tamanho_bytes: int
    data_captura: datetime | None
    local: Ponto | None
    origem_local: OrigemLocal | None
    sexo: Sexo | None
    status: StatusFoto
    erro: str | None
    tentativas: int
    enviada_em: datetime
    processada_em: datetime | None
    url_miniatura: str | None
    url_media: str | None
    url_original: str | None
    identificacao: IdentificacaoOut | None
    # Espécie final: a revisão mais recente, se houver; senão, o modelo
    especie: str | None
    origem_especie: OrigemEspecie | None
    revisada: bool
    revisao: RevisaoOut | None

    @classmethod
    def de(cls, f: Foto) -> "FotoOut":
        lat, lon = lat_lon(f.local)
        ident = f.identificacao
        return cls(
            id=f.id,
            coleta_id=f.coleta_id,
            nome_original=f.nome_original,
            largura=f.largura,
            altura=f.altura,
            tamanho_bytes=f.tamanho_bytes,
            data_captura=f.data_captura,
            local=Ponto(latitude=lat, longitude=lon) if lat is not None else None,
            origem_local=f.origem_local,
            sexo=f.sexo,
            status=f.status,
            erro=f.erro,
            tentativas=f.tentativas,
            enviada_em=f.enviada_em,
            processada_em=f.processada_em,
            url_miniatura=url_assinada(f.miniatura),
            url_media=url_assinada(f.media),
            url_original=url_assinada(f.arquivo),
            identificacao=IdentificacaoOut(
                identificada=ident.identificada,
                especie=ident.especie.nome_cientifico if ident.especie else None,
                confianca=ident.confianca,
                deteccoes=ident.deteccoes,
                versao_modelo=ident.modelo.versao if ident.modelo else None,
                criado_em=ident.criado_em,
            )
            if ident
            else None,
            especie=f.especie.nome_cientifico if f.especie else None,
            origem_especie=f.origem_especie,
            revisada=f.revisada,
            revisao=RevisaoOut(
                acao=rev.acao,
                especie=rev.especie.nome_cientifico if rev.especie else None,
                observacao=rev.observacao,
                revisor=rev.usuario.nome if rev.usuario else None,
                perfil_revisor=rev.perfil_revisor,
                criado_em=rev.criado_em,
            )
            if (rev := f.revisao)
            else None,
        )


class FotoAtualizar(BaseModel):
    """Envie "local": null para apagar a localização da foto."""

    local: Ponto | None = None
    sexo: Sexo | None = None


class Rejeitada(BaseModel):
    arquivo: str
    motivo: str


class EnvioOut(BaseModel):
    aceitas: list[FotoOut]
    rejeitadas: list[Rejeitada]


class PaginaFotos(BaseModel):
    itens: list[FotoOut]
    total: int
    pagina: int
    por_pagina: int


class PaginaColetas(BaseModel):
    itens: list[ColetaOut]
    total: int
    pagina: int
    por_pagina: int


# --- Revisões, resumo e espécies (etapa 3) ----------------------------------

# "Euglossa cognata", "Euglossa sp.", "Eulaema (Apeulaema) nigrita", "Euglossa aff. cognata"
_NOME_CIENTIFICO = re.compile(
    r"^[A-Z][a-z]+( \([A-Z][a-z]+\))?( (aff\.|cf\.))? ([a-z][a-z-]+|sp\.)( [a-z][a-z-]+)?$"
)


class RevisaoIn(BaseModel):
    """Revisão de uma pessoa sobre o resultado da foto.

    - confirmar: a espécie atual está certa
    - corrigir: informe a espécie certa em "especie" (nome científico)
    - nao_identificavel: não dá para identificar por esta foto
    - restaurar: desfaz as revisões e volta a valer o resultado do modelo
    """

    acao: Literal["confirmar", "corrigir", "nao_identificavel", "restaurar"]
    especie: str | None = Field(default=None, max_length=200)
    observacao: str | None = Field(default=None, max_length=2000)

    @field_validator("especie", "observacao", mode="before")
    @classmethod
    def _limpar(cls, v):
        if isinstance(v, str):
            v = " ".join(v.split())
            return v or None
        return v

    @field_validator("especie")
    @classmethod
    def _nome(cls, v):
        if v is not None and not _NOME_CIENTIFICO.match(v):
            raise ValueError(
                "Use o nome científico: gênero com inicial maiúscula e espécie em minúsculas "
                "(ex.: Euglossa cognata, ou Euglossa sp. quando a espécie é desconhecida)"
            )
        return v


class EspecieNoResumo(BaseModel):
    id: int
    nome: str
    quantidade: int
    porcentagem: float  # sobre as fotos identificadas (não identificadas ficam de fora)
    revisadas: int
    confianca_media: (
        float | None
    )  # média do modelo nas fotos em que ele acertou/indicou esta espécie


class ResumoColeta(BaseModel):
    total: int
    concluidas: int
    pendentes: int
    erro: int
    identificadas: int
    nao_identificadas: int
    revisadas: int
    especies: list[EspecieNoResumo]


class EspecieOut(BaseModel):
    id: int
    nome_cientifico: str
    sensivel: bool
    raio_ofuscacao_km: float
    reconhecida_pelo_modelo: bool


# --- Mapa (etapa 4) ------------------------------------------------------------


class AdminEspecieIn(BaseModel):
    sensivel: bool | None = None
    raio_ofuscacao_km: float | None = Field(default=None, ge=1, le=100)
