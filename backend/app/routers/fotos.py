"""Fotos: detalhes, localização, sexo, reprocessar e excluir."""

import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import usuario_atual
from app.fila import enfileirar_fotos
from app.geo import ponto
from app.models import Foto, OrigemLocal, Perfil, StatusFoto, Usuario
from app.routers.coletas import apagar_arquivos
from app.schemas_coletas import FotoAtualizar, FotoOut
from app.security import agora

router = APIRouter(prefix="/fotos", tags=["Fotos"])

# Uma foto "processando" há mais tempo que isso provavelmente travou (ex.: worker reiniciado)
TRAVADA_APOS = timedelta(minutes=15)


def obter_foto(db: Session, foto_id: uuid.UUID, usuario: Usuario) -> Foto:
    foto = db.get(Foto, foto_id)
    if foto is None or (foto.usuario_id != usuario.id and usuario.perfil != Perfil.admin):
        raise HTTPException(404, "Foto não encontrada.")
    return foto


@router.get("/{foto_id}", response_model=FotoOut)
def obter(
    foto_id: uuid.UUID, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)
):
    return FotoOut.de(obter_foto(db, foto_id, usuario))


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
    db.refresh(foto)
    return FotoOut.de(foto)


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
    db.refresh(foto)
    return FotoOut.de(foto)


@router.delete("/{foto_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(
    foto_id: uuid.UUID, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)
):
    foto = obter_foto(db, foto_id, usuario)
    arquivos = [c for c in (foto.arquivo, foto.miniatura, foto.media) if c]
    db.delete(foto)
    db.commit()
    apagar_arquivos(arquivos)
