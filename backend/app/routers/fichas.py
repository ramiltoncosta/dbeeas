"""Fichas das espécies.

- Público (sem login): catálogo das espécies e a ficha de cada uma.
- Administrador: escreve, revisa e publica as fichas, e envia a imagem.

O texto aceita uma formatação simples, desenhada pelo site:
parágrafos separados por linha em branco, listas com "- " no começo da linha,
**negrito** e *itálico* (para nomes científicos).
"""

import re
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.armazenamento import get_armazenamento, url_assinada
from app.config import get_settings
from app.db import get_db
from app.deps import exigir_admin
from app.exportacao import NOMES_UF
from app.imagens import ImagemInvalida, analisar, reduzir
from app.models import Coleta, Especie, FichaEspecie, Foto, StatusFoto, Usuario
from app.routers.especies import nomes_do_modelo
from app.schemas_especies import (
    EspecieDetalhe,
    EspecieResumo,
    EstadoOcorrencia,
    EstatisticasEspecie,
    FichaIn,
    FichaOut,
)

publico = APIRouter(prefix="/publico/especies", tags=["Público"])
admin = APIRouter(prefix="/admin/especies", tags=["Administração"])

TAMANHO_RESUMO = 220


def resumo(texto: str | None) -> str | None:
    """Primeiro parágrafo, sem as marcas de formatação, cortado num tamanho curto."""
    if not texto:
        return None
    primeiro = texto.split("\n\n", 1)[0]
    primeiro = re.sub(r"^\s*-\s+", "", primeiro, flags=re.M)
    primeiro = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", primeiro)
    primeiro = " ".join(primeiro.split())
    if len(primeiro) <= TAMANHO_RESUMO:
        return primeiro
    return primeiro[:TAMANHO_RESUMO].rsplit(" ", 1)[0].rstrip(".,;:") + "…"


def ficha_out(f: FichaEspecie | None, com_autor: bool = False) -> FichaOut:
    if f is None:
        return FichaOut(
            nome_popular=None,
            autoria=None,
            descricao=None,
            caracteristicas=None,
            distribuicao=None,
            fontes=None,
            url_imagem=None,
            credito_imagem=None,
            publicada=False,
            atualizado_em=None,
        )
    return FichaOut(
        nome_popular=f.nome_popular,
        autoria=f.autoria,
        descricao=f.descricao,
        caracteristicas=f.caracteristicas,
        distribuicao=f.distribuicao,
        fontes=f.fontes,
        url_imagem=url_assinada(f.imagem),
        credito_imagem=f.credito_imagem,
        publicada=f.publicada,
        atualizado_em=f.atualizado_em,
        atualizado_por=(f.atualizado_por.nome if f.atualizado_por else None) if com_autor else None,
    )


# Ocorrências públicas: fotos concluídas de coletas que aparecem no mapa geral
def _ocorrencias_publicas():
    return (
        select(Foto)
        .join(Coleta, Coleta.id == Foto.coleta_id)
        .where(Foto.status == StatusFoto.concluida, Coleta.publica_no_mapa.is_(True))
    )


def _visivel(e: Especie, f: FichaEspecie | None, do_modelo: set[str]) -> bool:
    """No catálogo público: espécies que o modelo reconhece ou com ficha publicada."""
    return e.nome_cientifico in do_modelo or bool(f and f.publicada)


def _resumo_especie(
    e: Especie, f: FichaEspecie | None, do_modelo: set[str], ocorrencias: int
) -> dict:
    publicada = bool(f and f.publicada)
    return dict(
        id=e.id,
        nome_cientifico=e.nome_cientifico,
        nome_popular=f.nome_popular if publicada else None,
        autoria=f.autoria if publicada else None,
        resumo=resumo(f.descricao) if publicada else None,
        url_imagem=url_assinada(f.imagem) if publicada else None,
        reconhecida_pelo_modelo=e.nome_cientifico in do_modelo,
        ficha_publicada=publicada,
        ocorrencias=ocorrencias,
    )


@publico.get("", response_model=list[EspecieResumo])
def catalogo(db: Session = Depends(get_db)):
    """Espécies que o DBeeAS reconhece, com o resumo da ficha (quando publicada)."""
    do_modelo = nomes_do_modelo(db)
    fichas = {f.especie_id: f for f in db.scalars(select(FichaEspecie))}
    sub = _ocorrencias_publicas().subquery()
    contagem = dict(
        db.execute(select(sub.c.especie_id, func.count()).group_by(sub.c.especie_id)).all()
    )
    return [
        EspecieResumo(**_resumo_especie(e, fichas.get(e.id), do_modelo, contagem.get(e.id, 0)))
        for e in db.scalars(select(Especie).order_by(Especie.nome_cientifico))
        if _visivel(e, fichas.get(e.id), do_modelo)
    ]


@publico.get("/{especie_id}", response_model=EspecieDetalhe)
def detalhe(especie_id: int, db: Session = Depends(get_db)):
    e = db.get(Especie, especie_id)
    f = db.get(FichaEspecie, especie_id)
    do_modelo = nomes_do_modelo(db)
    if e is None or not _visivel(e, f, do_modelo):
        raise HTTPException(404, "Espécie não encontrada.")

    sub = _ocorrencias_publicas().where(Foto.especie_id == e.id).subquery()
    total, coletas = db.execute(
        select(func.count(), func.count(func.distinct(sub.c.coleta_id)))
    ).one()
    estados = db.execute(
        select(Coleta.uf, func.count())
        .select_from(sub)
        .join(Coleta, Coleta.id == sub.c.coleta_id)
        .where(Coleta.uf.is_not(None))
        .group_by(Coleta.uf)
        .order_by(func.count().desc(), Coleta.uf)
    ).all()
    # Ano: da data da foto; sem ela, da data da coleta
    ano = func.extract("year", func.coalesce(sub.c.data_captura, Coleta.data_coleta))
    primeiro, ultimo = db.execute(
        select(func.min(ano), func.max(ano))
        .select_from(sub)
        .join(Coleta, Coleta.id == sub.c.coleta_id)
    ).one()

    return EspecieDetalhe(
        **_resumo_especie(e, f, do_modelo, total),
        sensivel=e.sensivel,
        ficha=ficha_out(f) if f and f.publicada else None,
        estatisticas=EstatisticasEspecie(
            ocorrencias=total,
            coletas=coletas,
            estados=[
                EstadoOcorrencia(uf=uf, nome=NOMES_UF.get(uf, uf), ocorrencias=n)
                for uf, n in estados
            ],
            primeiro_ano=int(primeiro) if primeiro else None,
            ultimo_ano=int(ultimo) if ultimo else None,
        ),
    )


# --- Administrador --------------------------------------------------------------


def _especie(db: Session, especie_id: int) -> Especie:
    e = db.get(Especie, especie_id)
    if e is None:
        raise HTTPException(404, "Espécie não encontrada.")
    return e


def _ficha(db: Session, especie_id: int, admin_: Usuario) -> FichaEspecie:
    f = db.get(FichaEspecie, especie_id)
    if f is None:
        f = FichaEspecie(especie_id=especie_id, publicada=False)
        db.add(f)
    f.atualizado_por_id = admin_.id
    return f


@admin.get("/{especie_id}/ficha", response_model=FichaOut)
def ler_ficha(especie_id: int, _: Usuario = Depends(exigir_admin), db: Session = Depends(get_db)):
    """Ficha completa, inclusive rascunho (não publicada)."""
    _especie(db, especie_id)
    return ficha_out(db.get(FichaEspecie, especie_id), com_autor=True)


@admin.put("/{especie_id}/ficha", response_model=FichaOut)
def salvar_ficha(
    especie_id: int,
    dados: FichaIn,
    admin_: Usuario = Depends(exigir_admin),
    db: Session = Depends(get_db),
):
    _especie(db, especie_id)
    if dados.publicada and not dados.descricao:
        raise HTTPException(400, "Escreva pelo menos a descrição antes de publicar.")
    f = _ficha(db, especie_id, admin_)
    for campo, valor in dados.model_dump().items():
        setattr(f, campo, valor)
    db.commit()
    db.refresh(f)
    return ficha_out(f, com_autor=True)


@admin.post("/{especie_id}/ficha/imagem", response_model=FichaOut)
def enviar_imagem(
    especie_id: int,
    arquivo: UploadFile = File(...),
    admin_: Usuario = Depends(exigir_admin),
    db: Session = Depends(get_db),
):
    """Imagem da ficha. É reduzida para até 1600 px e perde os metadados (GPS)."""
    _especie(db, especie_id)
    limite = get_settings().upload_max_mb * 1024 * 1024
    dados = arquivo.file.read(limite + 1)
    if len(dados) > limite:
        raise HTTPException(413, f"Imagem maior que {get_settings().upload_max_mb} MB.")
    try:
        analisar(dados)
        jpeg = reduzir(dados, 1600, qualidade=85)
    except ImagemInvalida as e:
        raise HTTPException(400, str(e)) from None

    arm = get_armazenamento()
    chave = f"fichas/{especie_id}/{uuid.uuid4().hex}.jpg"
    arm.salvar(chave, jpeg)
    f = _ficha(db, especie_id, admin_)
    antiga, f.imagem = f.imagem, chave
    db.commit()
    if antiga:
        arm.apagar(antiga)
    db.refresh(f)
    return ficha_out(f, com_autor=True)


@admin.delete("/{especie_id}/ficha/imagem", response_model=FichaOut)
def remover_imagem(
    especie_id: int, admin_: Usuario = Depends(exigir_admin), db: Session = Depends(get_db)
):
    _especie(db, especie_id)
    f = _ficha(db, especie_id, admin_)
    antiga, f.imagem = f.imagem, None
    db.commit()
    if antiga:
        get_armazenamento().apagar(antiga)
    db.refresh(f)
    return ficha_out(f, com_autor=True)
