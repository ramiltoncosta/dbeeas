"""Identificação rápida de uma foto, sem criar coleta (nada é guardado).

Conta no limite de fotos do plano, como as fotos das coletas.
"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import detector
from app.config import get_settings
from app.db import get_db
from app.deps import usuario_atual
from app.imagens import ImagemInvalida, analisar, preparar_para_detector
from app.models import Usuario
from app.planos import Cota

router = APIRouter(tags=["Identificação rápida"])


@router.post("/identificar")
def identificar(
    arquivo: UploadFile = File(..., description="Foto da asa (JPEG, PNG ou WEBP)"),
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    """Envia uma foto e recebe a espécie na hora, com a imagem anotada (caixas desenhadas).

    Para várias fotos, use as coletas: elas são processadas na fila e ficam guardadas.
    """
    limite = get_settings().upload_max_mb * 1024 * 1024
    dados = arquivo.file.read(limite + 1)
    if len(dados) > limite:
        raise HTTPException(413, f"Arquivo maior que {get_settings().upload_max_mb} MB.")
    try:
        analisar(dados)
        corpo, mime = preparar_para_detector(dados)
    except ImagemInvalida as e:
        raise HTTPException(415, str(e)) from e

    # Reserva uma foto do saldo e libera a trava antes de chamar o detector (leva segundos)
    cota = Cota(db, usuario)
    if not cota.pegar("identificacoes_rapidas"):
        db.rollback()
        raise HTTPException(403, cota.situacao.motivo_bloqueio)
    db.commit()

    try:
        return detector.detectar(corpo, mime, arquivo.filename or "foto", True)
    except (detector.ImagemRecusada, detector.DetectorIndisponivel) as e:
        # Não identificou: devolve a foto ao saldo
        Cota(db, usuario).devolver("identificacoes_rapidas")
        db.commit()
        if isinstance(e, detector.ImagemRecusada):
            raise HTTPException(415, str(e)) from e
        raise HTTPException(
            503, "O serviço de identificação está indisponível. Tente em instantes."
        ) from e
