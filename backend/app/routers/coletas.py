"""Coletas e envio de fotos."""

import hashlib
import logging
import uuid
from typing import Literal

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
from app.models import (
    Coleta,
    Especie,
    Exportacao,
    Foto,
    Identificacao,
    OrigemLocal,
    Perfil,
    Revisao,
    StatusFoto,
    Usuario,
)
from app.planos import Cota
from app.schemas_coletas import (
    ColetaAtualizar,
    ColetaIn,
    ColetaOut,
    Contagem,
    EnvioOut,
    EspecieNoResumo,
    FotoOut,
    PaginaColetas,
    PaginaFotos,
    Rejeitada,
    ResumoColeta,
)

log = logging.getLogger("dbeeas.coletas")

# Carrega junto tudo o que a resposta de uma foto precisa (evita uma consulta por foto)
CARREGAR_FOTO = (
    selectinload(Foto.identificacoes).selectinload(Identificacao.especie),
    selectinload(Foto.identificacoes).selectinload(Identificacao.modelo),
    selectinload(Foto.especie),
    selectinload(Foto.revisoes).selectinload(Revisao.especie),
    selectinload(Foto.revisoes).selectinload(Revisao.usuario),
)
router = APIRouter(prefix="/coletas", tags=["Coletas"])


def obter_coleta(db: Session, coleta_id: uuid.UUID, usuario: Usuario) -> Coleta:
    """Busca a coleta. Só o dono e o administrador têm acesso."""
    coleta = db.get(Coleta, coleta_id)
    if coleta is None or (coleta.usuario_id != usuario.id and usuario.perfil != Perfil.admin):
        # 404 também para coletas de outras pessoas: não revela que existem
        raise HTTPException(404, "Coleta não encontrada.")
    return coleta


def confianca_atual():
    """Confiança da identificação mais recente da foto (subconsulta)."""
    return (
        select(Identificacao.confianca)
        .where(Identificacao.foto_id == Foto.id)
        .order_by(Identificacao.criado_em.desc())
        .limit(1)
        .scalar_subquery()
    )


def para_revisar():
    """Fotos que vale a pena uma pessoa conferir: identificadas pelo modelo com
    confiança baixa e ainda sem revisão."""
    return (
        (Foto.status == StatusFoto.concluida)
        & Foto.especie_id.is_not(None)
        & Foto.revisada.is_(False)
        & (confianca_atual() < get_settings().confianca_revisao)
    )


def contar_fotos(db: Session, coleta_ids: list[uuid.UUID]) -> dict[uuid.UUID, Contagem]:
    if not coleta_ids:
        return {}

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
            soma(concluida & Foto.especie_id.is_not(None)),
            soma(concluida & Foto.especie_id.is_(None)),
        )
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
    if "publica_no_mapa" in enviados and dados.publica_no_mapa is None:
        enviados = enviados - {"publica_no_mapa"}
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
    ] + list(
        db.scalars(
            select(Exportacao.arquivo).where(
                Exportacao.coleta_id == coleta.id, Exportacao.arquivo.is_not(None)
            )
        )
    )
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

    # Limite do plano: conta para o dono da coleta (trava o saldo até o fim do envio)
    dono = usuario if coleta.usuario_id == usuario.id else db.get(Usuario, coleta.usuario_id)
    cota = Cota(db, dono)
    if not cota.situacao.pode_enviar:
        db.rollback()
        raise HTTPException(403, cota.situacao.motivo_bloqueio)

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
        if not cota.pegar():
            motivo = "Limite de fotos do plano atingido neste mês."
            rejeitadas.append(Rejeitada(arquivo=nome, motivo=motivo))
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
        .options(*CARREGAR_FOTO)
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
    especie_id: int | None = Query(None, description="Só as fotos desta espécie (espécie final)"),
    grupo: Literal["nao_identificadas", "pendentes", "revisadas", "para_revisar"] | None = Query(
        None,
        description="nao_identificadas, pendentes (na fila ou processando), revisadas ou "
        "para_revisar (confiança baixa e sem revisão)",
    ),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(60, ge=1, le=500),
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    coleta = obter_coleta(db, coleta_id, usuario)
    filtros = [Foto.coleta_id == coleta.id]
    if status_foto:
        filtros.append(Foto.status == status_foto)
    if especie_id is not None:
        filtros.append(Foto.especie_id == especie_id)
    if grupo == "nao_identificadas":
        filtros += [Foto.status == StatusFoto.concluida, Foto.especie_id.is_(None)]
    elif grupo == "pendentes":
        filtros.append(Foto.status.in_([StatusFoto.na_fila, StatusFoto.processando]))
    elif grupo == "revisadas":
        filtros.append(Foto.revisada.is_(True))
    elif grupo == "para_revisar":
        filtros.append(para_revisar())
    total = db.scalar(select(func.count()).select_from(Foto).where(*filtros))
    fotos = db.scalars(
        select(Foto)
        .where(*filtros)
        .options(*CARREGAR_FOTO)
        .order_by(Foto.enviada_em, Foto.nome_original)
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
    ).all()
    return PaginaFotos(
        itens=[FotoOut.de(f) for f in fotos], total=total, pagina=pagina, por_pagina=por_pagina
    )


@router.get("/{coleta_id}/resumo", response_model=ResumoColeta)
def resumo(
    coleta_id: uuid.UUID, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)
):
    """Quantas fotos de cada espécie e a porcentagem de cada uma.

    As porcentagens são calculadas só sobre as fotos identificadas: as não identificadas
    aparecem separadas, para não distorcer a proporção entre as espécies.
    """
    coleta = obter_coleta(db, coleta_id, usuario)
    c = contar_fotos(db, [coleta.id]).get(coleta.id, Contagem())

    ident = (
        select(Identificacao.foto_id, Identificacao.especie_id, Identificacao.confianca)
        .distinct(Identificacao.foto_id)
        .order_by(Identificacao.foto_id, Identificacao.criado_em.desc())
        .subquery()
    )
    # Confiança média do modelo só nas fotos em que o modelo indicou a mesma espécie final
    conf_mesma = case((ident.c.especie_id == Foto.especie_id, ident.c.confianca))
    linhas = db.execute(
        select(
            Especie.id,
            Especie.nome_cientifico,
            func.count(Foto.id),
            func.sum(case((Foto.revisada, 1), else_=0)),
            func.avg(conf_mesma),
        )
        .join(Especie, Especie.id == Foto.especie_id)
        .outerjoin(ident, ident.c.foto_id == Foto.id)
        .where(Foto.coleta_id == coleta.id, Foto.status == StatusFoto.concluida)
        .group_by(Especie.id, Especie.nome_cientifico)
        .order_by(func.count(Foto.id).desc(), Especie.nome_cientifico)
    ).all()

    revisadas = db.scalar(
        select(func.count())
        .select_from(Foto)
        .where(Foto.coleta_id == coleta.id, Foto.revisada.is_(True))
    )
    return ResumoColeta(
        total=c.total,
        concluidas=c.concluidas,
        pendentes=c.na_fila + c.processando,
        erro=c.erro,
        identificadas=c.identificadas,
        nao_identificadas=c.nao_identificadas,
        revisadas=revisadas,
        para_revisar=db.scalar(
            select(func.count())
            .select_from(Foto)
            .where(Foto.coleta_id == coleta.id, para_revisar())
        ),
        limite_confianca_revisao=get_settings().confianca_revisao,
        especies=[
            EspecieNoResumo(
                id=eid,
                nome=nome,
                quantidade=qtd,
                porcentagem=round(qtd / c.identificadas * 100, 1) if c.identificadas else 0,
                revisadas=rev or 0,
                confianca_media=round(float(conf), 4) if conf is not None else None,
            )
            for eid, nome, qtd, rev, conf in linhas
        ],
    )
