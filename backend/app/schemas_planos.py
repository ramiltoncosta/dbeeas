"""Formatos de entrada e saída de planos e assinaturas."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import Assinatura, StatusAssinatura
from app.planos import Situacao


class PlanoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    nome: str
    descricao: str | None
    preco_mensal_centavos: int | None
    limite_fotos_mes: int | None
    permite_exportacao: bool
    publico: bool
    ordem: int


class PlanoIn(BaseModel):
    codigo: str = Field(pattern=r"^[a-z0-9_-]{2,40}$")
    nome: str = Field(min_length=2, max_length=80)
    descricao: str | None = Field(None, max_length=1000)
    preco_mensal_centavos: int | None = Field(None, ge=0)
    limite_fotos_mes: int | None = Field(None, ge=1)
    permite_exportacao: bool = True
    publico: bool = True
    ordem: int = 0


class PlanoAtualizar(BaseModel):
    """Só os campos enviados mudam. Enviar null em preço ou limite = "sob consulta"/"sem limite"."""

    nome: str | None = Field(None, min_length=2, max_length=80)
    descricao: str | None = Field(None, max_length=1000)
    preco_mensal_centavos: int | None = Field(None, ge=0)
    limite_fotos_mes: int | None = Field(None, ge=1)
    permite_exportacao: bool | None = None
    publico: bool | None = None
    ordem: int | None = None


class AssinaturaOut(BaseModel):
    id: uuid.UUID
    plano: PlanoOut
    status: StatusAssinatura
    inicio: datetime
    fim: datetime | None
    origem: str
    observacao: str | None
    criado_em: datetime
    alterado_por: str | None = None

    @classmethod
    def de(cls, a: Assinatura | None, com_autor: bool = False) -> "AssinaturaOut | None":
        if a is None:
            return None
        return cls(
            id=a.id,
            plano=PlanoOut.model_validate(a.plano),
            status=a.status,
            inicio=a.inicio,
            fim=a.fim,
            origem=a.origem,
            observacao=a.observacao if com_autor else None,
            criado_em=a.criado_em,
            alterado_por=(a.alterado_por.nome if a.alterado_por else None) if com_autor else None,
        )


class UsoOut(BaseModel):
    mes: date
    fotos: int
    identificacoes_rapidas: int
    usadas: int
    limite: int | None
    restantes: int | None


class MeuPlano(BaseModel):
    # teste, ativa, suspensa, cancelada, expirada, sem_plano ou ilimitado (administrador)
    status: str
    plano: PlanoOut | None
    assinatura: AssinaturaOut | None
    uso: UsoOut
    pode_enviar: bool
    motivo_bloqueio: str | None
    permite_exportacao: bool
    pedido: AssinaturaOut | None  # pedido de plano ainda não ativado


def uso_out(s: Situacao, mes: date) -> UsoOut:
    return UsoOut(
        mes=mes,
        fotos=s.fotos,
        identificacoes_rapidas=s.identificacoes_rapidas,
        usadas=s.usadas,
        limite=s.limite,
        restantes=s.restantes,
    )


class PedidoIn(BaseModel):
    plano_id: int


class PedidoOut(BaseModel):
    mensagem: str
    url_pagamento: str | None = None
    pedido: AssinaturaOut


class AdminAssinaturaIn(BaseModel):
    """O administrador define o plano de um usuário (cria uma linha nova no histórico)."""

    plano_id: int
    status: StatusAssinatura = StatusAssinatura.ativa
    # Prazo: data exata ou número de dias a partir de agora. Nenhum dos dois = sem prazo.
    fim: datetime | None = None
    dias: int | None = Field(None, ge=1, le=3660)
    observacao: str | None = Field(None, max_length=1000)


class ResumoPlanoUsuario(BaseModel):
    """Na lista de usuários do administrador."""

    status: str
    plano: str | None
    fim: datetime | None
    usadas: int
    limite: int | None
    pedido: str | None  # nome do plano pedido e ainda não ativado
