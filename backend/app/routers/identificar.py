"""Identificação rápida de uma foto, sem criar coleta (nada é guardado)."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from app import detector
from app.config import get_settings
from app.deps import usuario_atual
from app.imagens import ImagemInvalida, analisar, preparar_para_detector
from app.models import Usuario

router = APIRouter(tags=["Identificação rápida"])


@router.post("/identificar")
async def identificar(
    arquivo: UploadFile = File(..., description="Foto da asa (JPEG, PNG ou WEBP)"),
    _: Usuario = Depends(usuario_atual),
):
    """Envia uma foto e recebe a espécie na hora, com a imagem anotada (caixas desenhadas).

    Para várias fotos, use as coletas: elas são processadas na fila e ficam guardadas.
    """
    limite = get_settings().upload_max_mb * 1024 * 1024
    dados = await arquivo.read(limite + 1)
    if len(dados) > limite:
        raise HTTPException(413, f"Arquivo maior que {get_settings().upload_max_mb} MB.")
    try:
        analisar(dados)
        corpo, mime = preparar_para_detector(dados)
    except ImagemInvalida as e:
        raise HTTPException(415, str(e)) from e

    try:
        return await run_in_threadpool(
            detector.detectar, corpo, mime, arquivo.filename or "foto", True
        )
    except detector.ImagemRecusada as e:
        raise HTTPException(415, str(e)) from e
    except detector.DetectorIndisponivel as e:
        raise HTTPException(
            503, "O serviço de identificação está indisponível. Tente em instantes."
        ) from e
