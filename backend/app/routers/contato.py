"""Formulário de contato da página pública e a caixa de mensagens do administrador."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import exigir_admin
from app.emails import enviar_email
from app.models import MensagemContato, Usuario
from app.ratelimit import limiter
from app.schemas import Mensagem
from app.schemas_especies import ContatoIn, MensagemAtualizar, MensagemOut, PaginaMensagens

publico = APIRouter(prefix="/publico", tags=["Público"])
admin = APIRouter(prefix="/admin/mensagens", tags=["Administração"])

ASSUNTOS = {
    "duvida": "Dúvida",
    "planos": "Planos e assinaturas",
    "institucional": "Uso institucional (órgão público, universidade)",
    "parceria": "Parceria",
    "imprensa": "Imprensa",
    "outro": "Outro assunto",
}

RESPOSTA = "Mensagem recebida. Responderemos pelo e-mail informado."


@publico.post("/contato", response_model=Mensagem, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")
def contato(request: Request, dados: ContatoIn, db: Session = Depends(get_db)):
    if dados.site:
        # Robô preencheu o campo escondido: finge que deu certo e não guarda nada
        return Mensagem(mensagem=RESPOSTA)
    m = MensagemContato(**dados.model_dump(exclude={"site"}))
    db.add(m)
    db.commit()
    enviar_email(
        get_settings().email_contato,
        f"DBeeAS – Contato: {ASSUNTOS[dados.assunto]} – {dados.nome}",
        f"Nome: {dados.nome}\nE-mail: {dados.email}\n"
        f"Instituição: {dados.instituicao or '-'}\nAssunto: {ASSUNTOS[dados.assunto]}\n\n"
        f"{dados.mensagem}\n",
    )
    return Mensagem(mensagem=RESPOSTA)


@admin.get("", response_model=PaginaMensagens)
def listar(
    somente_nao_respondidas: bool = False,
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(20, ge=1, le=100),
    _: Usuario = Depends(exigir_admin),
    db: Session = Depends(get_db),
):
    filtros = [MensagemContato.respondida.is_(False)] if somente_nao_respondidas else []
    total = db.scalar(select(func.count()).select_from(MensagemContato).where(*filtros))
    nao_resp = db.scalar(
        select(func.count())
        .select_from(MensagemContato)
        .where(MensagemContato.respondida.is_(False))
    )
    itens = db.scalars(
        select(MensagemContato)
        .where(*filtros)
        .order_by(MensagemContato.criado_em.desc())
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
    ).all()
    return PaginaMensagens(
        itens=[MensagemOut.model_validate(m) for m in itens], total=total, nao_respondidas=nao_resp
    )


@admin.patch("/{mensagem_id}", response_model=MensagemOut)
def atualizar(
    mensagem_id: uuid.UUID,
    dados: MensagemAtualizar,
    _: Usuario = Depends(exigir_admin),
    db: Session = Depends(get_db),
):
    m = db.get(MensagemContato, mensagem_id)
    if m is None:
        raise HTTPException(404, "Mensagem não encontrada.")
    m.respondida = dados.respondida
    db.commit()
    return MensagemOut.model_validate(m)
