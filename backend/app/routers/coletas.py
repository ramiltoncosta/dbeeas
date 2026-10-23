"""Coletas e envio de fotos."""

import hashlib
import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from app.armazenamento import get_armazenamento
from app.config import get_settings
from app.db import get_db
from app.deps import usuario_atual
from app.fila import enfileirar_fotos
from app.geo import ponto
from app.imagens import ImagemInvalida, analisar
from app.models import Coleta, Foto, Identificacao, OrigemLocal, Perfil, StatusFoto, Usuario
from app.schemas_coletas import (
    ColetaAtualizar,
    ColetaIn,
    ColetaOut,
    Contagem,
    EnvioOut,
    FotoOut,
    PaginaColetas,
    PaginaFotos,
    Rejeitada,
)

log = logging.getLogger("dbeeas.coletas")
router = APIRouter(prefix="/coletas", tags=["Coletas"])


def obter_coleta(db: Session, coleta_id: uuid.UUID, usuario: Usuario) -> Coleta:
    """Busca a coleta. Só o dono e o administrador têm acesso."""
    coleta = db.get(Coleta, coleta_id)
    if coleta is None or (coleta.usuario_id != usuario.id and usuario.perfil != Perfil.admin):
        # 404 também para coletas de outras pessoas: não revela que existem
        raise HTTPException(404, "Coleta não encontrada.")
    return coleta


def _ultima_identificacao():
    """Subconsulta: a identificação mais recente de cada foto."""
    return (
        select(Identificacao.foto_id, Identificacao.identificada)
        .distinct(Identificacao.foto_id)
        .order_by(Identificacao.foto_id, Identificacao.criado_em.desc())
        .subquery()
    )


def contar_fotos(db: Session, coleta_ids: list[uuid.UUID]) -> dict[uuid.UUID, Contagem]:
    if not coleta_ids:
        return {}
    ident = _ultima_identificacao()

    def soma(cond):
        return func.sum(case((cond, 1), else_=0))

    concluida = Foto.status == StatusFoto.concluida
    linhas = db.execute(
        select(
            Foto.coleta_id,
            func.count(Foto.id),
            soma(Foto.status == StatusFoto.na_fila),
            soma(Foto.status == StatusFoto.processando),
            soma(concluida),
            soma(Foto.status == StatusFoto.erro),
            soma(concluida & ident.c.identificada.is_(True)),
            soma(concluida & ident.c.identificada.is_not(True)),
        )
        .outerjoin(ident, ident.c.foto_id == Foto.id)
        .where(Foto.coleta_id.in_(coleta_ids))
        .group_by(Foto.coleta_id)
    ).all()
    return {
        linha[0]: Contagem(
            total=linha[1],
            na_fila=linha[2],
            processando=linha[3],
            concluidas=linha[4],
            erro=linha[5],
            identificadas=linha[6],
            nao_identificadas=linha[7],
        )
        for linha in linhas
    }


@router.get("", response_model=PaginaColetas)
def listar(
    busca: str | None = None,
    todas: bool = Query(False, description="Somente administrador: coletas de todos"),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(20, ge=1, le=100),
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    filtros = []
    if not (todas and usuario.perfil == Perfil.admin):
        filtros.append(Coleta.usuario_id == usuario.id)
    if busca:
        termo = f"%{busca.strip()}%"
        filtros.append(Coleta.nome.ilike(termo) | Coleta.municipio.ilike(termo))

    total = db.scalar(select(func.count()).select_from(Coleta).where(*filtros))
    coletas = db.scalars(
        select(Coleta)
        .where(*filtros)
        .order_by(Coleta.criado_em.desc())
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
    ).all()
    contagens = contar_fotos(db, [c.id for c in coletas])
    return PaginaColetas(
        itens=[ColetaOut.de(c, contagens.get(c.id)) for c in coletas],
        total=total,
        pagina=pagina,
        por_pagina=por_pagina,
    )


@router.post("", response_model=ColetaOut, status_code=status.HTTP_201_CREATED)
def criar(
    dados: ColetaIn, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)
):
    campos = dados.model_dump(exclude={"local"})
    coleta = Coleta(usuario_id=usuario.id, **campos)
    if dados.local:
        coleta.local = ponto(dados.local.latitude, dados.local.longitude)
    db.add(coleta)
    db.commit()
    db.refresh(coleta)
    return ColetaOut.de(coleta)


@router.get("/{coleta_id}", response_model=ColetaOut)
def obter(
    coleta_id: uuid.UUID, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)
):
    coleta = obter_coleta(db, coleta_id, usuario)
    return ColetaOut.de(coleta, contar_fotos(db, [coleta.id]).get(coleta.id))


@router.patch("/{coleta_id}", response_model=ColetaOut)
def atualizar(
    coleta_id: uuid.UUID,
    dados: ColetaAtualizar,
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    coleta = obter_coleta(db, coleta_id, usuario)
    enviados = dados.model_fields_set
    if "nome" in enviados and dados.nome is None:
        raise HTTPException(422, "O nome da coleta é obrigatório.")
    for campo in enviados - {"local"}:
        setattr(coleta, campo, getattr(dados, campo))
    if "local" in enviados:
        coleta.local = ponto(dados.local.latitude, dados.local.longitude) if dados.local else None
    db.commit()
    db.refresh(coleta)
    return ColetaOut.de(coleta, contar_fotos(db, [coleta.id]).get(coleta.id))


@router.delete("/{coleta_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(
    coleta_id: uuid.UUID, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)
):
    """Exclui a coleta, as fotos e os arquivos. Não pode ser desfeito."""
    coleta = obter_coleta(db, coleta_id, usuario)
    arquivos = [
        chave
        for f in db.scalars(select(Foto).where(Foto.coleta_id == coleta.id))
        for chave in (f.arquivo, f.miniatura, f.media)
        if chave
    ]
    db.delete(coleta)
    db.commit()
    apagar_arquivos(arquivos)


def apagar_arquivos(chaves: list[str]) -> None:
    arm = get_armazenamento()
    for chave in chaves:
        try:
            arm.apagar(chave)
        except OSError:
            log.exception("Não foi possível apagar o arquivo %s", chave)


@router.get("/{coleta_id}/progresso", response_model=Contagem)
def progresso(
    coleta_id: uuid.UUID, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)
):
    """Andamento do processamento. A tela consulta a cada poucos segundos."""
    coleta = obter_coleta(db, coleta_id, usuario)
    return contar_fotos(db, [coleta.id]).get(coleta.id, Contagem())


@router.post("/{coleta_id}/fotos", response_model=EnvioOut)
def enviar_fotos(
    coleta_id: uuid.UUID,
    arquivos: list[UploadFile] = File(..., description="Fotos das asas (JPEG, PNG ou WEBP)"),
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    """Recebe uma ou mais fotos e coloca na fila de processamento.

    Cada foto é conferida (tipo real do arquivo e tamanho). A localização e a data
    são lidas dos metadados (EXIF) quando existirem. Fotos repetidas na mesma
    coleta são ignoradas.
    """
    s = get_settings()
    coleta = obter_coleta(db, coleta_id, usuario)
    if len(arquivos) > s.max_fotos_por_envio:
        raise HTTPException(413, f"Envie no máximo {s.max_fotos_por_envio} fotos por vez.")

    limite = s.upload_max_mb * 1024 * 1024
    arm = get_armazenamento()
    existentes = set(db.scalars(select(Foto.sha256).where(Foto.coleta_id == coleta.id)))
    aceitas: list[Foto] = []
    rejeitadas: list[Rejeitada] = []
    salvos: list[str] = []

    for arquivo in arquivos:
        nome = (arquivo.filename or "foto")[:255]
        dados = arquivo.file.read(limite + 1)
        if len(dados) > limite:
            rejeitadas.append(Rejeitada(arquivo=nome, motivo=f"Maior que {s.upload_max_mb} MB."))
            continue
        try:
            info = analisar(dados)
        except ImagemInvalida as e:
            rejeitadas.append(Rejeitada(arquivo=nome, motivo=str(e)))
            continue

        sha = hashlib.sha256(dados).hexdigest()
        if sha in existentes:
            rejeitadas.append(Rejeitada(arquivo=nome, motivo="Esta foto já está na coleta."))
            continue
        existentes.add(sha)

        foto_id = uuid.uuid4()
        chave = f"fotos/{coleta.usuario_id}/{coleta.id}/{foto_id}.{info.extensao}"
        arm.salvar(chave, dados)
        salvos.append(chave)

        foto = Foto(
            id=foto_id,
            coleta_id=coleta.id,
            usuario_id=coleta.usuario_id,
            arquivo=chave,
            nome_original=nome,
            tipo_mime=info.tipo_mime,
            tamanho_bytes=len(dados),
            sha256=sha,
            largura=info.largura,
            altura=info.altura,
            data_captura=info.data_captura,
            status=StatusFoto.na_fila,
        )
        if info.latitude is not None:
            foto.local = ponto(info.latitude, info.longitude)
            foto.origem_local = OrigemLocal.exif
        db.add(foto)
        aceitas.append(foto)

    try:
        db.commit()
    except Exception:
        db.rollback()
        apagar_arquivos(salvos)  # nada fica pela metade
        raise

    ids = [str(f.id) for f in aceitas]
    try:
        enfileirar_fotos(ids)
    except Exception:
        # As fotos ficam salvas como "na fila"; dá para reprocessar depois
        log.exception("Não foi possível colocar as fotos na fila")

    fotos = db.scalars(
        select(Foto)
        .where(Foto.id.in_([f.id for f in aceitas]))
        .options(selectinload(Foto.identificacoes))
        .execution_options(populate_existing=True)
    ).all()
    por_id = {f.id: f for f in fotos}
    return EnvioOut(
        aceitas=[FotoOut.de(por_id[f.id]) for f in aceitas if f.id in por_id],
        rejeitadas=rejeitadas,
    )


@router.get("/{coleta_id}/fotos", response_model=PaginaFotos)
def listar_fotos(
    coleta_id: uuid.UUID,
    status_foto: StatusFoto | None = Query(None, alias="status"),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(60, ge=1, le=200),
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    coleta = obter_coleta(db, coleta_id, usuario)
    filtros = [Foto.coleta_id == coleta.id]
    if status_foto:
        filtros.append(Foto.status == status_foto)
    total = db.scalar(select(func.count()).select_from(Foto).where(*filtros))
    fotos = db.scalars(
        select(Foto)
        .where(*filtros)
        .options(
            selectinload(Foto.identificacoes).selectinload(Identificacao.especie),
            selectinload(Foto.identificacoes).selectinload(Identificacao.modelo),
        )
        .order_by(Foto.enviada_em, Foto.nome_original)
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
    ).all()
    return PaginaFotos(
        itens=[FotoOut.de(f) for f in fotos], total=total, pagina=pagina, por_pagina=por_pagina
    )
