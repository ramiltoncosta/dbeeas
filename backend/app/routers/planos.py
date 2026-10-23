"""Planos e assinaturas.

- Público: lista dos planos (página inicial).
- Usuário: "Meu plano" (plano, prazo e uso do mês) e pedido de plano.
- Administrador: cria e edita planos e define o plano de cada usuário.
- Serviço de pagamento: endereço que recebe os avisos (webhook).
"""

import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import planos as regras
from app.db import get_db
from app.deps import exigir_admin, usuario_atual
from app.models import Assinatura, Plano, StatusAssinatura, Usuario
from app.pagamentos import AssinaturaInvalida, aplicar_evento, get_gateway
from app.schemas import Mensagem
from app.schemas_planos import (
    AdminAssinaturaIn,
    AssinaturaOut,
    MeuPlano,
    PedidoIn,
    PedidoOut,
    PlanoAtualizar,
    PlanoIn,
    PlanoOut,
    uso_out,
)
from app.security import agora

publico = APIRouter(tags=["Planos"])
eu = APIRouter(prefix="/eu/plano", tags=["Planos"])
admin = APIRouter(prefix="/admin", tags=["Administração"])
pagamentos = APIRouter(prefix="/pagamentos", tags=["Pagamentos"])


@publico.get("/planos", response_model=list[PlanoOut])
def listar_publicos(db: Session = Depends(get_db)):
    """Planos oferecidos (sem login)."""
    return db.scalars(select(Plano).where(Plano.publico.is_(True)).order_by(Plano.ordem, Plano.id))


def meu_plano(db: Session, usuario: Usuario) -> MeuPlano:
    s = regras.situacao(db, usuario)
    return MeuPlano(
        status=s.status,
        plano=PlanoOut.model_validate(s.plano) if s.plano else None,
        assinatura=AssinaturaOut.de(s.assinatura),
        uso=uso_out(s, regras.mes_atual()),
        pode_enviar=s.pode_enviar,
        motivo_bloqueio=s.motivo_bloqueio,
        permite_exportacao=s.permite_exportacao,
        pedido=AssinaturaOut.de(regras.pedido_pendente(db, usuario.id)),
    )


@eu.get("", response_model=MeuPlano)
def ver(usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    """Plano atual, prazo e quanto já foi usado no mês."""
    return meu_plano(db, usuario)


@eu.post("/pedido", response_model=PedidoOut, status_code=status.HTTP_201_CREATED)
def pedir(
    dados: PedidoIn, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)
):
    """Pede um plano. Com o pagamento manual, a equipe recebe o pedido e ativa pelo site."""
    plano = db.get(Plano, dados.plano_id)
    if plano is None or not plano.publico:
        raise HTTPException(404, "Plano não encontrado.")
    pendente = regras.pedido_pendente(db, usuario.id)
    if pendente and pendente.plano_id == plano.id:
        raise HTTPException(409, "Você já pediu este plano. Aguarde a ativação.")

    gateway = get_gateway()
    pedido = Assinatura(
        id=uuid.uuid4(),
        usuario_id=usuario.id,
        plano_id=plano.id,
        status=StatusAssinatura.pendente,
        origem=gateway.nome,
        observacao="Pedido feito pelo usuário",
    )
    cobranca = gateway.iniciar_assinatura(usuario, plano, str(pedido.id))
    pedido.codigo_externo = cobranca.codigo_externo
    db.add(pedido)
    db.commit()
    db.refresh(pedido)
    return PedidoOut(
        mensagem=cobranca.mensagem,
        url_pagamento=cobranca.url_pagamento,
        pedido=AssinaturaOut.de(pedido),
    )


@eu.delete("/pedido", response_model=Mensagem)
def desistir(usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    pendente = regras.pedido_pendente(db, usuario.id)
    if pendente is None:
        raise HTTPException(404, "Não há pedido de plano em aberto.")
    if pendente.codigo_externo:
        get_gateway().cancelar_assinatura(pendente.codigo_externo)
    # Um pedido nunca chegou a valer: pode ser apagado sem perder histórico de uso
    db.delete(pendente)
    db.commit()
    return Mensagem(mensagem="Pedido cancelado.")


# --- Administrador --------------------------------------------------------------


@admin.get("/planos", response_model=list[PlanoOut])
def admin_listar(_: Usuario = Depends(exigir_admin), db: Session = Depends(get_db)):
    return db.scalars(select(Plano).order_by(Plano.ordem, Plano.id))


@admin.post("/planos", response_model=PlanoOut, status_code=status.HTTP_201_CREATED)
def admin_criar(dados: PlanoIn, _: Usuario = Depends(exigir_admin), db: Session = Depends(get_db)):
    plano = Plano(**dados.model_dump())
    db.add(plano)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Já existe um plano com este código.") from None
    return plano


@admin.patch("/planos/{plano_id}", response_model=PlanoOut)
def admin_atualizar(
    plano_id: int,
    dados: PlanoAtualizar,
    _: Usuario = Depends(exigir_admin),
    db: Session = Depends(get_db),
):
    plano = db.get(Plano, plano_id)
    if plano is None:
        raise HTTPException(404, "Plano não encontrado.")
    for campo in dados.model_fields_set:
        valor = getattr(dados, campo)
        if valor is None and campo not in (
            "preco_mensal_centavos",
            "limite_fotos_mes",
            "descricao",
        ):
            continue  # nome, ordem etc. não podem ficar vazios
        setattr(plano, campo, valor)
    db.commit()
    return plano


def _usuario(db: Session, usuario_id: uuid.UUID) -> Usuario:
    u = db.get(Usuario, usuario_id)
    if u is None:
        raise HTTPException(404, "Usuário não encontrado.")
    return u


@admin.get("/usuarios/{usuario_id}/plano", response_model=MeuPlano)
def admin_ver_plano(
    usuario_id: uuid.UUID, _: Usuario = Depends(exigir_admin), db: Session = Depends(get_db)
):
    return meu_plano(db, _usuario(db, usuario_id))


@admin.get("/usuarios/{usuario_id}/assinaturas", response_model=list[AssinaturaOut])
def admin_historico(
    usuario_id: uuid.UUID, _: Usuario = Depends(exigir_admin), db: Session = Depends(get_db)
):
    """Todas as assinaturas e pedidos do usuário, da mais recente para a mais antiga."""
    _usuario(db, usuario_id)
    itens = db.scalars(
        select(Assinatura)
        .where(Assinatura.usuario_id == usuario_id)
        .order_by(Assinatura.criado_em.desc())
    )
    return [AssinaturaOut.de(a, com_autor=True) for a in itens]


@admin.post(
    "/usuarios/{usuario_id}/assinaturas",
    response_model=MeuPlano,
    status_code=status.HTTP_201_CREATED,
)
def admin_definir(
    usuario_id: uuid.UUID,
    dados: AdminAssinaturaIn,
    adm: Usuario = Depends(exigir_admin),
    db: Session = Depends(get_db),
):
    """Ativa, troca, suspende ou cancela o plano de um usuário (pagamento manual)."""
    usuario = _usuario(db, usuario_id)
    if db.get(Plano, dados.plano_id) is None:
        raise HTTPException(404, "Plano não encontrado.")
    if dados.status == StatusAssinatura.pendente:
        raise HTTPException(422, "Escolha teste, ativa, suspensa ou cancelada.")
    fim = dados.fim
    if dados.dias:
        fim = agora() + timedelta(days=dados.dias)
    if dados.status == StatusAssinatura.cancelada and fim is None:
        fim = agora()
    db.add(
        Assinatura(
            usuario_id=usuario.id,
            plano_id=dados.plano_id,
            status=dados.status,
            fim=fim,
            origem="manual",
            observacao=dados.observacao,
            alterado_por_id=adm.id,
        )
    )
    db.commit()
    return meu_plano(db, usuario)


# --- Serviço de pagamento -------------------------------------------------------


@pagamentos.post("/webhook/{gateway}", response_model=Mensagem, include_in_schema=False)
async def webhook(gateway: str, request: Request, db: Session = Depends(get_db)):
    """Recebe os avisos do serviço de pagamento (pagamento confirmado, atrasado...)."""
    g = get_gateway()
    if gateway != g.nome:
        raise HTTPException(404, "Serviço de pagamento não configurado.")
    try:
        evento = g.ler_webhook(dict(request.headers), await request.body())
    except AssinaturaInvalida:
        raise HTTPException(401, "Aviso não autenticado.") from None
    if evento:
        await run_in_threadpool(aplicar_evento, db, g.nome, evento)
    return Mensagem(mensagem="ok")
