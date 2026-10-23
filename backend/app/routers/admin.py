"""Administração de usuários."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import exigir_admin
from app.models import Perfil, Usuario
from app.schemas import AdminAtualizarUsuarioIn, PaginaUsuarios, UsuarioAdminOut
from app.sessao import revogar_sessoes

router = APIRouter(prefix="/admin", tags=["Administração"])


@router.get("/usuarios", response_model=PaginaUsuarios)
def listar_usuarios(
    busca: str | None = Query(None, description="Parte do nome, e-mail ou instituição"),
    perfil: Perfil | None = None,
    aguardando_aprovacao: bool = False,
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

    total = db.scalar(select(func.count()).select_from(Usuario).where(*filtros))
    itens = db.scalars(
        select(Usuario)
        .where(*filtros)
        .order_by(Usuario.criado_em.desc())
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
    ).all()
    return PaginaUsuarios(itens=itens, total=total, pagina=pagina, por_pagina=por_pagina)


@router.get("/usuarios/{usuario_id}", response_model=UsuarioAdminOut)
def obter_usuario(
    usuario_id: uuid.UUID, _: Usuario = Depends(exigir_admin), db: Session = Depends(get_db)
):
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(404, "Usuário não encontrado.")
    return usuario


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
    return usuario
