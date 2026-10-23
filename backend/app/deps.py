"""Dependências comuns: usuário logado, permissões."""

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Perfil, Usuario
from app.security import ler_access_token

_bearer = HTTPBearer(auto_error=False)


def usuario_atual(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Usuario:
    erro = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Sessão inválida ou expirada. Entre novamente.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if cred is None:
        raise erro
    payload = ler_access_token(cred.credentials)
    if payload is None:
        raise erro
    try:
        usuario = db.get(Usuario, uuid.UUID(payload["sub"]))
    except (KeyError, ValueError):
        raise erro from None
    if usuario is None or not usuario.ativo:
        raise erro
    return usuario


def exigir_admin(usuario: Usuario = Depends(usuario_atual)) -> Usuario:
    if usuario.perfil != Perfil.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Acesso restrito a administradores.")
    return usuario


def pode_ver_localizacao_exata(usuario: Usuario, dono_id: uuid.UUID) -> bool:
    """Quem vê o ponto exato de espécies sensíveis.

    Regra definida para o DBeeAS: o dono da foto, o administrador e pesquisadores.
    Com PESQUISADOR_REQUER_APROVACAO=true, o pesquisador precisa ser aprovado.
    (Usado a partir da etapa do mapa.)
    """
    if usuario.id == dono_id or usuario.perfil == Perfil.admin:
        return True
    if usuario.perfil == Perfil.pesquisador:
        if get_settings().pesquisador_requer_aprovacao:
            return usuario.perfil_aprovado
        return True
    return False
