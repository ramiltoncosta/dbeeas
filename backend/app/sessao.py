"""Criação e encerramento de sessões (access token + refresh token)."""

from datetime import timedelta

from fastapi import Request, Response
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import TipoToken, Token, Usuario
from app.schemas import TokenOut, UsuarioOut
from app.security import agora, criar_access_token, gerar_token_opaco

COOKIE_REFRESH = "dbeeas_refresh"
COOKIE_PATH = "/v1/auth"


def eh_aplicativo(request: Request) -> bool:
    """O aplicativo de celular se identifica com o cabeçalho X-Cliente: app."""
    return request.headers.get("x-cliente", "").lower() == "app"


def iniciar_sessao(db: Session, usuario: Usuario, request: Request, response: Response) -> TokenOut:
    s = get_settings()
    access, expira = criar_access_token(usuario.id, usuario.perfil.value)

    refresh, refresh_hash = gerar_token_opaco()
    db.add(
        Token(
            usuario_id=usuario.id,
            tipo=TipoToken.refresh,
            token_hash=refresh_hash,
            expira_em=agora() + timedelta(days=s.refresh_token_dias),
        )
    )
    db.commit()

    app = eh_aplicativo(request)
    if not app:
        # No navegador, o refresh token fica num cookie que o JavaScript não consegue ler
        response.set_cookie(
            COOKIE_REFRESH,
            refresh,
            max_age=s.refresh_token_dias * 86400,
            httponly=True,
            secure=s.cookie_seguro,
            samesite="strict",
            path=COOKIE_PATH,
            domain=s.cookie_dominio,
        )

    return TokenOut(
        access_token=access,
        expires_in=expira,
        refresh_token=refresh if app else None,
        usuario=UsuarioOut.model_validate(usuario),
    )


def limpar_cookie(response: Response) -> None:
    s = get_settings()
    response.delete_cookie(
        COOKIE_REFRESH,
        path=COOKIE_PATH,
        domain=s.cookie_dominio,
        secure=s.cookie_seguro,
        httponly=True,
        samesite="strict",
    )


def revogar_sessoes(db: Session, usuario: Usuario) -> None:
    """Encerra todas as sessões do usuário (ex.: depois de trocar a senha)."""
    db.execute(
        update(Token)
        .where(
            Token.usuario_id == usuario.id,
            Token.tipo == TipoToken.refresh,
            Token.usado_em.is_(None),
        )
        .values(usado_em=agora())
    )
