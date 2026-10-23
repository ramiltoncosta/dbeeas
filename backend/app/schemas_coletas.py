"""Formatos de entrada e saída de coletas e fotos."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.armazenamento import url_assinada
from app.geo import lat_lon
from app.models import Bioma, Coleta, Foto, OrigemLocal, Sexo, StatusFoto

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
