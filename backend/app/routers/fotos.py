"""Fotos: detalhes, localização, sexo, reprocessar e excluir."""

import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import usuario_atual
from app.especies import obter_ou_criar_especie, recalcular_especie_final
from app.fila import enfileirar_fotos
from app.geo import ponto
from app.models import AcaoRevisao, Foto, OrigemLocal, Perfil, Revisao, StatusFoto, Usuario
from app.routers.coletas import CARREGAR_FOTO, apagar_arquivos
from app.schemas_coletas import FotoAtualizar, FotoOut, RevisaoIn
from app.security import agora

router = APIRouter(prefix="/fotos", tags=["Fotos"])

# Uma foto "processando" há mais tempo que isso provavelmente travou (ex.: worker reiniciado)
TRAVADA_APOS = timedelta(minutes=15)


def obter_foto(db: Session, foto_id: uuid.UUID, usuario: Usuario) -> Foto:
    foto = db.get(Foto, foto_id)
    if foto is None or (foto.usuario_id != usuario.id and usuario.perfil != Perfil.admin):
        raise HTTPException(404, "Foto não encontrada.")
    return foto


def _foto_completa(db: Session, foto_id: uuid.UUID) -> Foto:
    return db.scalar(
        select(Foto)
        .where(Foto.id == foto_id)
        .options(*CARREGAR_FOTO)
        .execution_options(populate_existing=True)
    )


@router.get("/{foto_id}", response_model=FotoOut)
def obter(
    foto_id: uuid.UUID, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)
):
    obter_foto(db, foto_id, usuario)
    return FotoOut.de(_foto_completa(db, foto_id))


@router.patch("/{foto_id}", response_model=FotoOut)
def atualizar(
    foto_id: uuid.UUID,
    dados: FotoAtualizar,
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    """Marca a localização no mapa (substitui a do EXIF) e/ou o sexo do espécime."""
    foto = obter_foto(db, foto_id, usuario)
    if "local" in dados.model_fields_set:
        if dados.local:
            foto.local = ponto(dados.local.latitude, dados.local.longitude)
            foto.origem_local = OrigemLocal.manual
        else:
            foto.local = None
            foto.origem_local = None
    if "sexo" in dados.model_fields_set:
        foto.sexo = dados.sexo
    db.commit()
    return FotoOut.de(_foto_completa(db, foto.id))


@router.post("/{foto_id}/reprocessar", response_model=FotoOut)
def reprocessar(
    foto_id: uuid.UUID, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)
):
    """Coloca de novo na fila uma foto que deu erro (ou que travou no processamento)."""
    foto = obter_foto(db, foto_id, usuario)
    travada = foto.status in (StatusFoto.processando, StatusFoto.na_fila) and (
        agora() - foto.enviada_em > TRAVADA_APOS
    )
    if foto.status != StatusFoto.erro and not travada:
        raise HTTPException(409, "Esta foto não precisa ser reprocessada.")
    foto.status = StatusFoto.na_fila
    foto.tentativas = 0
    foto.erro = None
    db.commit()
    enfileirar_fotos([str(foto.id)])
    return FotoOut.de(_foto_completa(db, foto.id))


@router.delete("/{foto_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(
    foto_id: uuid.UUID, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)
):
    foto = obter_foto(db, foto_id, usuario)
    arquivos = [c for c in (foto.arquivo, foto.miniatura, foto.media) if c]
    db.delete(foto)
    db.commit()
    apagar_arquivos(arquivos)


@router.post("/{foto_id}/revisao", response_model=FotoOut)
def revisar(
    foto_id: uuid.UUID,
    dados: RevisaoIn,
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    """Confirma, corrige ou marca como não identificável o resultado de uma foto.

    Cada revisão fica guardada no histórico (quem, quando, o que o modelo dizia).
    A predição original do modelo nunca é alterada.
    """
    foto = obter_foto(db, foto_id, usuario)
    if foto.status != StatusFoto.concluida:
        raise HTTPException(409, "Espere a foto terminar de ser processada para revisar.")

    acao = {
        "confirmar": AcaoRevisao.confirmou,
        "corrigir": AcaoRevisao.corrigiu,
        "nao_identificavel": AcaoRevisao.nao_identificavel,
        "restaurar": AcaoRevisao.restaurou,
    }[dados.acao]

    especie_id = None
    if acao == AcaoRevisao.confirmou:
        if foto.especie_id is None:
            raise HTTPException(
                409, 'Não há espécie para confirmar. Use "corrigir" e informe a espécie.'
            )
        especie_id = foto.especie_id
    elif acao == AcaoRevisao.corrigiu:
        if not dados.especie:
            raise HTTPException(422, "Informe a espécie correta.")
        especie_id = obter_ou_criar_especie(db, dados.especie).id
    elif acao == AcaoRevisao.restaurou and not foto.revisada:
        raise HTTPException(409, "Esta foto não tem revisão para desfazer.")

    ident = foto.identificacao
    db.add(
        Revisao(
            foto_id=foto.id,
            usuario_id=usuario.id,
            perfil_revisor=usuario.perfil,
            acao=acao,
            especie_id=especie_id,
            identificacao_id=ident.id if ident else None,
            observacao=dados.observacao,
        )
    )
    db.flush()
    db.refresh(foto, ["revisoes"])
    recalcular_especie_final(foto)
    db.commit()
    return FotoOut.de(_foto_completa(db, foto.id))
