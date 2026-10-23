"""Entrega das imagens por links assinados (com prazo de validade)."""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.armazenamento import ArmazenamentoLocal, assinatura_valida, get_armazenamento

router = APIRouter(prefix="/arquivos", tags=["Arquivos"])


@router.get("/{chave:path}", include_in_schema=False)
def baixar(chave: str, expira: int = Query(...), assinatura: str = Query(...)):
    if not assinatura_valida(chave, expira, assinatura):
        raise HTTPException(403, "Link inválido ou expirado.")
    arm = get_armazenamento()
    if not isinstance(arm, ArmazenamentoLocal):  # pragma: no cover
        raise HTTPException(501, "Armazenamento não suportado")
    try:
        caminho = arm.caminho(chave)
    except ValueError:
        raise HTTPException(404, "Arquivo não encontrado.") from None
    if not caminho.is_file():
        raise HTTPException(404, "Arquivo não encontrado.")
    if caminho.suffix == ".zip":
        # Exportações: o navegador baixa com o nome do arquivo, em vez de abrir
        return FileResponse(
            caminho,
            filename=caminho.name,
            media_type="application/zip",
            headers={"Cache-Control": "private, no-store"},
        )
    return FileResponse(
        caminho,
        # Pode ficar no cache do navegador enquanto o link valer
        headers={"Cache-Control": "private, max-age=3600"},
    )
