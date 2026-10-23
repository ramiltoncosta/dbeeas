"""Exportação da coleta (ZIP por espécie + planilha Darwin Core).

O ZIP é gerado no worker. A tela pede a exportação, acompanha o status e,
quando fica pronta, recebe um link assinado para baixar.
"""

import uuid
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.armazenamento import url_assinada
from app.db import get_db
from app.deps import usuario_atual
from app.exportacao import apagar_expiradas
from app.fila import enfileirar_exportacao
from app.models import (
    Exportacao,
    Foto,
    Perfil,
    StatusExportacao,
    TipoImagemExportacao,
    Usuario,
)
from app.planos import situacao
from app.routers.coletas import apagar_arquivos, obter_coleta
from app.security import agora

router = APIRouter(tags=["Exportação"])

# Uma exportação "gerando" há mais tempo que isso travou (worker reiniciado, por exemplo)
PRAZO_TRAVADA = timedelta(hours=2)


class ExportacaoIn(BaseModel):
    tipo_imagem: TipoImagemExportacao = TipoImagemExportacao.original


class ExportacaoOut(BaseModel):
    id: uuid.UUID
    coleta_id: uuid.UUID
    tipo_imagem: TipoImagemExportacao
    status: Literal["na_fila", "gerando", "pronta", "erro", "expirada"]
    total_fotos: int | None
    tamanho_bytes: int | None
    erro: str | None
    criado_em: datetime
    concluida_em: datetime | None
    expira_em: datetime | None
    url_download: str | None

    @classmethod
    def de(cls, e: Exportacao) -> "ExportacaoOut":
        situacao = e.status.value
        url = None
        if e.status == StatusExportacao.pronta:
            if not e.arquivo or (e.expira_em and e.expira_em < agora()):
                situacao = "expirada"
            else:
                url = url_assinada(e.arquivo)
        return cls(
            id=e.id,
            coleta_id=e.coleta_id,
            tipo_imagem=e.tipo_imagem,
            status=situacao,
            total_fotos=e.total_fotos,
            tamanho_bytes=e.tamanho_bytes,
            erro=e.erro,
            criado_em=e.criado_em,
            concluida_em=e.concluida_em,
            expira_em=e.expira_em,
            url_download=url,
        )


EM_ANDAMENTO = (StatusExportacao.na_fila, StatusExportacao.gerando)


@router.post(
    "/coletas/{coleta_id}/exportacoes",
    response_model=ExportacaoOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def exportar(
    coleta_id: uuid.UUID,
    dados: ExportacaoIn,
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    """Pede o ZIP da coleta. O arquivo é gerado em segundo plano."""
    coleta = obter_coleta(db, coleta_id, usuario)
    if not situacao(db, usuario).permite_exportacao:
        raise HTTPException(
            403, "Seu plano não inclui a exportação. Veja os planos em “Meu plano”."
        )
    apagar_expiradas(db)

    total = db.scalar(select(func.count()).select_from(Foto).where(Foto.coleta_id == coleta.id))
    if not total:
        raise HTTPException(400, "A coleta ainda não tem fotos para exportar.")

    anteriores = db.scalars(
        select(Exportacao).where(
            Exportacao.coleta_id == coleta.id,
            Exportacao.tipo_imagem == dados.tipo_imagem,
        )
    ).all()
    for e in anteriores:
        if e.status in EM_ANDAMENTO:
            if e.criado_em > agora() - PRAZO_TRAVADA:
                # Já tem uma sendo gerada: devolve a mesma, sem duplicar o trabalho
                return ExportacaoOut.de(e)
            e.status = StatusExportacao.erro
            e.erro = "A geração demorou demais e foi cancelada."

    # O arquivo novo substitui os anteriores do mesmo tipo (economiza espaço no servidor)
    antigos = [e.arquivo for e in anteriores if e.arquivo]
    for e in anteriores:
        e.arquivo = None

    exp = Exportacao(coleta_id=coleta.id, usuario_id=usuario.id, tipo_imagem=dados.tipo_imagem)
    db.add(exp)
    db.commit()
    apagar_arquivos(antigos)

    enfileirar_exportacao(str(exp.id))
    db.refresh(exp)
    return ExportacaoOut.de(exp)


@router.get("/coletas/{coleta_id}/exportacoes", response_model=list[ExportacaoOut])
def listar(
    coleta_id: uuid.UUID, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)
):
    """Exportações recentes da coleta (as 10 últimas)."""
    coleta = obter_coleta(db, coleta_id, usuario)
    itens = db.scalars(
        select(Exportacao)
        .where(Exportacao.coleta_id == coleta.id)
        .order_by(Exportacao.criado_em.desc())
        .limit(10)
    ).all()
    return [ExportacaoOut.de(e) for e in itens]


@router.get("/exportacoes/{exportacao_id}", response_model=ExportacaoOut)
def obter(
    exportacao_id: uuid.UUID,
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    exp = db.get(Exportacao, exportacao_id)
    if exp is None or (exp.usuario_id != usuario.id and usuario.perfil != Perfil.admin):
        raise HTTPException(404, "Exportação não encontrada.")
    return ExportacaoOut.de(exp)
