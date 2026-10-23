"""Formatos de entrada e saída das fichas das espécies, do painel e do contato."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas_coletas import ColetaOut


def _texto(v):
    if isinstance(v, str):
        # Normaliza quebras de linha (Windows) e tira espaços das pontas
        v = v.replace("\r\n", "\n").strip()
        return v or None
    return v


# --- Fichas ---------------------------------------------------------------------


class FichaIn(BaseModel):
    nome_popular: str | None = Field(None, max_length=200)
    autoria: str | None = Field(None, max_length=200)
    descricao: str | None = Field(None, max_length=20000)
    caracteristicas: str | None = Field(None, max_length=20000)
    distribuicao: str | None = Field(None, max_length=20000)
    fontes: str | None = Field(None, max_length=20000)
    credito_imagem: str | None = Field(None, max_length=300)
    publicada: bool = False

    _limpar = field_validator(
        "nome_popular",
        "autoria",
        "descricao",
        "caracteristicas",
        "distribuicao",
        "fontes",
        "credito_imagem",
        mode="before",
    )(_texto)


class FichaOut(BaseModel):
    nome_popular: str | None
    autoria: str | None
    descricao: str | None
    caracteristicas: str | None
    distribuicao: str | None
    fontes: str | None
    url_imagem: str | None
    credito_imagem: str | None
    publicada: bool
    atualizado_em: datetime | None
    atualizado_por: str | None = None  # só para o administrador


class EspecieResumo(BaseModel):
    """Item do catálogo público de espécies."""

    id: int
    nome_cientifico: str
    nome_popular: str | None
    autoria: str | None
    resumo: str | None
    url_imagem: str | None
    reconhecida_pelo_modelo: bool
    ficha_publicada: bool
    ocorrencias: int


class EstadoOcorrencia(BaseModel):
    uf: str
    nome: str
    ocorrencias: int


class EstatisticasEspecie(BaseModel):
    """Números da plataforma. Só contam coletas que aparecem no mapa geral."""

    ocorrencias: int
    coletas: int
    estados: list[EstadoOcorrencia]
    primeiro_ano: int | None
    ultimo_ano: int | None


class EspecieDetalhe(EspecieResumo):
    sensivel: bool
    ficha: FichaOut | None
    estatisticas: EstatisticasEspecie


# --- Painel ---------------------------------------------------------------------


class TotaisPainel(BaseModel):
    coletas: int
    fotos: int
    identificadas: int
    nao_identificadas: int
    em_processamento: int
    com_erro: int
    revisadas: int
    especies: int
    fotos_mes: int  # enviadas no mês atual


class EspeciePainel(BaseModel):
    id: int
    nome: str
    quantidade: int
    porcentagem: float
    coletas: int


class PlataformaPainel(BaseModel):
    """Só para o administrador."""

    usuarios: int
    usuarios_novos_30d: int
    coletas: int
    fotos: int
    fotos_hoje: int
    na_fila: int
    com_erro: int
    mensagens_nao_respondidas: int


class ColetaParaRevisar(BaseModel):
    id: uuid.UUID
    nome: str
    fotos: int


class Painel(BaseModel):
    totais: TotaisPainel
    especies: list[EspeciePainel]
    ultimas_coletas: list[ColetaOut]
    # Fotos identificadas com confiança baixa e ainda sem revisão de uma pessoa
    para_revisar: int
    para_revisar_coletas: list[ColetaParaRevisar]
    limite_confianca_revisao: float
    plataforma: PlataformaPainel | None = None


# --- Contato --------------------------------------------------------------------

Assunto = Literal["duvida", "planos", "institucional", "parceria", "imprensa", "outro"]


class ContatoIn(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    email: EmailStr
    instituicao: str | None = Field(None, max_length=200)
    assunto: Assunto = "duvida"
    mensagem: str = Field(min_length=10, max_length=5000)
    # Campo escondido na tela: pessoas não preenchem, robôs sim
    site: str | None = None

    _limpar = field_validator("nome", "instituicao", "mensagem", mode="before")(_texto)


class MensagemOut(BaseModel):
    id: uuid.UUID
    nome: str
    email: str
    instituicao: str | None
    assunto: str
    mensagem: str
    respondida: bool
    criado_em: datetime

    model_config = {"from_attributes": True}


class PaginaMensagens(BaseModel):
    itens: list[MensagemOut]
    total: int
    nao_respondidas: int


class MensagemAtualizar(BaseModel):
    respondida: bool
