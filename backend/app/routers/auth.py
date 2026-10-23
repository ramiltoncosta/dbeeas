"""Cadastro, login, sessão e recuperação de senha."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import usuario_atual
from app.emails import email_redefinir_senha
from app.models import Perfil, TipoToken, Token, Usuario
from app.planos import criar_teste
from app.ratelimit import limiter
from app.schemas import (
    CadastroIn,
    EsqueciSenhaIn,
    LoginIn,
    Mensagem,
    RedefinirSenhaIn,
    RefreshIn,
    TokenOut,
    UsuarioOut,
)
from app.security import (
    agora,
    gerar_hash_senha,
    gerar_token_opaco,
    hash_token,
    verificar_senha,
)
from app.sessao import COOKIE_REFRESH, iniciar_sessao, limpar_cookie, revogar_sessoes

router = APIRouter(prefix="/auth", tags=["Autenticação"])
_limite = get_settings().limite_auth


@router.post("/cadastro", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(_limite)
def cadastro(
    request: Request, response: Response, dados: CadastroIn, db: Session = Depends(get_db)
):
    """Cria a conta e já inicia a sessão."""
    if not dados.aceite_termos:
        raise HTTPException(422, "É preciso aceitar os termos de uso e a política de privacidade.")

    if db.scalar(select(Usuario.id).where(Usuario.email == dados.email)):
        raise HTTPException(409, "Já existe uma conta com este e-mail.")

    perfil = Perfil(dados.perfil)
    momento = agora()
    usuario = Usuario(
        nome=dados.nome,
        email=dados.email,
        senha_hash=gerar_hash_senha(dados.senha),
        perfil=perfil,
        instituicao=dados.instituicao or None,
        perfil_aprovado=not (
            perfil == Perfil.pesquisador and get_settings().pesquisador_requer_aprovacao
        ),
        termos_aceitos_em=momento,
        consentimento_uso_fotos=dados.consentimento_uso_fotos,
        consentimento_uso_fotos_em=momento if dados.consentimento_uso_fotos else None,
        ultimo_login_em=momento,
    )
    db.add(usuario)
    db.flush()
    criar_teste(db, usuario)  # período de teste gratuito no plano do perfil
    return iniciar_sessao(db, usuario, request, response)


@router.post("/login", response_model=TokenOut)
@limiter.limit(_limite)
def login(request: Request, response: Response, dados: LoginIn, db: Session = Depends(get_db)):
    usuario = db.scalar(select(Usuario).where(Usuario.email == dados.email))
    # Mesma mensagem para e-mail inexistente e senha errada (não revela quais e-mails existem)
    if not verificar_senha(dados.senha, usuario.senha_hash if usuario else None):
        raise HTTPException(401, "E-mail ou senha incorretos.")
    if not usuario.ativo:
        raise HTTPException(403, "Esta conta está desativada. Fale com o suporte.")

    usuario.ultimo_login_em = agora()
    return iniciar_sessao(db, usuario, request, response)


@router.post("/refresh", response_model=TokenOut)
def refresh(
    request: Request,
    response: Response,
    dados: RefreshIn | None = None,
    db: Session = Depends(get_db),
):
    """Renova a sessão. O refresh token antigo é trocado por um novo (rotação)."""
    token = (dados.refresh_token if dados else None) or request.cookies.get(COOKIE_REFRESH)
    erro = HTTPException(401, "Sessão expirada. Entre novamente.")
    if not token:
        raise erro

    registro = db.scalar(
        select(Token).where(Token.token_hash == hash_token(token), Token.tipo == TipoToken.refresh)
    )
    if registro is None:
        limpar_cookie(response)
        raise erro

    usuario = registro.usuario
    if registro.usado_em is not None:
        # Um token já usado apareceu de novo: pode ter sido copiado por outra pessoa.
        # Por segurança, encerramos todas as sessões dessa conta.
        revogar_sessoes(db, usuario)
        db.commit()
        limpar_cookie(response)
        raise erro

    if registro.expira_em <= agora() or not usuario.ativo:
        limpar_cookie(response)
        raise erro

    registro.usado_em = agora()
    return iniciar_sessao(db, usuario, request, response)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    dados: RefreshIn | None = None,
    db: Session = Depends(get_db),
):
    token = (dados.refresh_token if dados else None) or request.cookies.get(COOKIE_REFRESH)
    if token:
        registro = db.scalar(select(Token).where(Token.token_hash == hash_token(token)))
        if registro and registro.usado_em is None:
            registro.usado_em = agora()
            db.commit()
    limpar_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/esqueci-senha", response_model=Mensagem, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
def esqueci_senha(request: Request, dados: EsqueciSenhaIn, db: Session = Depends(get_db)):
    """Envia o link de redefinição. A resposta é sempre a mesma, exista ou não a conta."""
    s = get_settings()
    usuario = db.scalar(select(Usuario).where(Usuario.email == dados.email))
    if usuario and usuario.ativo:
        token, token_hash = gerar_token_opaco()
        db.add(
            Token(
                usuario_id=usuario.id,
                tipo=TipoToken.redefinir_senha,
                token_hash=token_hash,
                expira_em=agora() + timedelta(minutes=s.redefinir_senha_minutos),
            )
        )
        db.commit()
        link = f"{s.frontend_url.rstrip('/')}/redefinir-senha?token={token}"
        email_redefinir_senha(usuario.email, usuario.nome, link, s.redefinir_senha_minutos)

    return Mensagem(
        mensagem="Se houver uma conta com este e-mail, enviaremos um link para redefinir a senha."
    )


@router.post("/redefinir-senha", response_model=Mensagem)
@limiter.limit(_limite)
def redefinir_senha(request: Request, dados: RedefinirSenhaIn, db: Session = Depends(get_db)):
    registro = db.scalar(
        select(Token).where(
            Token.token_hash == hash_token(dados.token),
            Token.tipo == TipoToken.redefinir_senha,
        )
    )
    if registro is None or registro.usado_em is not None or registro.expira_em <= agora():
        raise HTTPException(400, "Link inválido ou expirado. Peça um novo link.")

    usuario = registro.usuario
    usuario.senha_hash = gerar_hash_senha(dados.nova_senha)
    registro.usado_em = agora()
    revogar_sessoes(db, usuario)  # quem estava logado com a senha antiga é desconectado
    db.commit()
    return Mensagem(mensagem="Senha alterada. Entre com a nova senha.")


@router.get("/eu", response_model=UsuarioOut)
def eu(usuario: Usuario = Depends(usuario_atual)):
    """Dados do usuário logado."""
    return usuario
