"""Administração de usuários (com o plano e o uso de cada um)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.db import get_db
from app.deps import exigir_admin
from app.models import Assinatura, Perfil, StatusAssinatura, Usuario
from app.planos import pedido_pendente, situacao
from app.schemas import AdminAtualizarUsuarioIn, PaginaUsuarios, UsuarioAdminOut
from app.schemas_planos import ResumoPlanoUsuario
from app.sessao import revogar_sessoes

router = APIRouter(prefix="/admin", tags=["Administração"])


@router.get("/usuarios", response_model=PaginaUsuarios)
def listar_usuarios(
    busca: str | None = Query(None, description="Parte do nome, e-mail ou instituição"),
    perfil: Perfil | None = None,
    aguardando_aprovacao: bool = False,
    pedidos_de_plano: bool = Query(False, description="Só quem pediu um plano ainda não ativado"),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(20, ge=1, le=100),
    _: Usuario = Depends(exigir_admin),
    db: Session = Depends(get_db),
):
    filtros = []
    if busca:
        termo = f"%{busca.strip()}%"
        filtros.append(
            or_(
                Usuario.nome.ilike(termo),
                Usuario.email.ilike(termo),
                Usuario.instituicao.ilike(termo),
            )
        )
    if perfil:
        filtros.append(Usuario.perfil == perfil)
    if aguardando_aprovacao:
        filtros.append(Usuario.perfil_aprovado.is_(False))
    if pedidos_de_plano:
        # Tem um pedido mais novo que qualquer assinatura que já vale
        pedido = aliased(Assinatura)
        valendo = aliased(Assinatura)
        filtros.append(
            exists().where(
                pedido.usuario_id == Usuario.id,
                pedido.status == StatusAssinatura.pendente,
                ~exists().where(
                    valendo.usuario_id == Usuario.id,
                    valendo.status != StatusAssinatura.pendente,
                    valendo.criado_em > pedido.criado_em,
                ),
            )
        )

    total = db.scalar(select(func.count()).select_from(Usuario).where(*filtros))
    itens = db.scalars(
        select(Usuario)
        .where(*filtros)
        .order_by(Usuario.criado_em.desc())
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
    ).all()
    return PaginaUsuarios(
        itens=[com_plano(db, u) for u in itens], total=total, pagina=pagina, por_pagina=por_pagina
    )


def com_plano(db: Session, u: Usuario) -> UsuarioAdminOut:
    """Dados do usuário com o resumo do plano e do uso no mês."""
    s = situacao(db, u)
    pedido = pedido_pendente(db, u.id)
    out = UsuarioAdminOut.model_validate(u)
    out.plano = ResumoPlanoUsuario(
        status=s.status,
        plano=s.plano.nome if s.plano else None,
        fim=s.assinatura.fim if s.assinatura else None,
        usadas=s.usadas,
        limite=s.limite,
        pedido=pedido.plano.nome if pedido else None,
    )
    return out


@router.get("/usuarios/{usuario_id}", response_model=UsuarioAdminOut)
def obter_usuario(
    usuario_id: uuid.UUID, _: Usuario = Depends(exigir_admin), db: Session = Depends(get_db)
):
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(404, "Usuário não encontrado.")
    return com_plano(db, usuario)


@router.patch("/usuarios/{usuario_id}", response_model=UsuarioAdminOut)
def atualizar_usuario(
    usuario_id: uuid.UUID,
    dados: AdminAtualizarUsuarioIn,
    admin: Usuario = Depends(exigir_admin),
    db: Session = Depends(get_db),
):
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(404, "Usuário não encontrado.")
    if usuario.id == admin.id and (
        dados.ativo is False or (dados.perfil and dados.perfil != Perfil.admin)
    ):
        raise HTTPException(400, "Você não pode desativar nem rebaixar a sua própria conta.")

    if dados.perfil is not None:
        usuario.perfil = dados.perfil
    if dados.perfil_aprovado is not None:
        usuario.perfil_aprovado = dados.perfil_aprovado
    if dados.ativo is not None:
        usuario.ativo = dados.ativo
        if not dados.ativo:
            revogar_sessoes(db, usuario)  # desconecta na hora
    db.commit()
    return com_plano(db, usuario)
