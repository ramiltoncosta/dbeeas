"""Minha conta: atualizar dados, trocar senha e direitos da LGPD."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import usuario_atual
from app.models import Perfil, Usuario
from app.schemas import (
    AtualizarContaIn,
    ExcluirContaIn,
    TokenOut,
    TrocarSenhaIn,
    UsuarioOut,
)
from app.security import agora, gerar_hash_senha, verificar_senha
from app.sessao import iniciar_sessao, limpar_cookie, revogar_sessoes

router = APIRouter(prefix="/eu", tags=["Minha conta"])


@router.patch("", response_model=UsuarioOut)
def atualizar(
    dados: AtualizarContaIn,
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    if dados.nome is not None:
        usuario.nome = dados.nome.strip()
    if "instituicao" in dados.model_fields_set:
        usuario.instituicao = (dados.instituicao or "").strip() or None
    if (
        dados.consentimento_uso_fotos is not None
        and dados.consentimento_uso_fotos != usuario.consentimento_uso_fotos
    ):
        usuario.consentimento_uso_fotos = dados.consentimento_uso_fotos
        usuario.consentimento_uso_fotos_em = agora()
    db.commit()
    return usuario


@router.post("/senha", response_model=TokenOut)
def trocar_senha(
    dados: TrocarSenhaIn,
    request: Request,
    response: Response,
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    """Troca a senha. As outras sessões abertas são encerradas."""
    if not verificar_senha(dados.senha_atual, usuario.senha_hash):
        raise HTTPException(400, "Senha atual incorreta.")
    usuario.senha_hash = gerar_hash_senha(dados.nova_senha)
    revogar_sessoes(db, usuario)
    return iniciar_sessao(db, usuario, request, response)


@router.get("/dados")
def exportar_dados(usuario: Usuario = Depends(usuario_atual)):
    """LGPD: baixa todos os dados pessoais guardados sobre o usuário.

    Nas próximas etapas, este arquivo vai incluir também coletas e fotos.
    """
    dados = {
        "conta": {
            "id": str(usuario.id),
            "nome": usuario.nome,
            "email": usuario.email,
            "perfil": usuario.perfil.value,
            "instituicao": usuario.instituicao,
            "criado_em": usuario.criado_em.isoformat(),
            "ultimo_login_em": usuario.ultimo_login_em.isoformat()
            if usuario.ultimo_login_em
            else None,
        },
        "consentimentos": {
            "termos_aceitos_em": usuario.termos_aceitos_em.isoformat(),
            "uso_das_fotos_para_melhorar_o_modelo": usuario.consentimento_uso_fotos,
            "uso_das_fotos_atualizado_em": usuario.consentimento_uso_fotos_em.isoformat()
            if usuario.consentimento_uso_fotos_em
            else None,
        },
        "exportado_em": agora().isoformat(),
    }
    return JSONResponse(
        dados,
        headers={"Content-Disposition": 'attachment; filename="meus-dados-dbeeas.json"'},
    )


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def excluir_conta(
    dados: ExcluirContaIn,
    response: Response,
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    """LGPD: exclui a conta e todos os dados do usuário. Não pode ser desfeito."""
    if not verificar_senha(dados.senha, usuario.senha_hash):
        raise HTTPException(400, "Senha incorreta.")
    if usuario.perfil == Perfil.admin:
        admins = db.scalar(
            select(func.count())
            .select_from(Usuario)
            .where(Usuario.perfil == Perfil.admin, Usuario.ativo.is_(True))
        )
        if admins <= 1:
            raise HTTPException(
                400, "Você é o único administrador. Crie outro antes de excluir sua conta."
            )
    db.delete(usuario)
    db.commit()
    limpar_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
