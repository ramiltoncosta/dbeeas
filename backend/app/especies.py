"""Espécie final de cada foto e revisões feitas por pessoas."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AcaoRevisao, Especie, Foto, OrigemEspecie


def obter_ou_criar(db: Session, modelo, filtro: dict, **extra):
    """Busca um registro; se não existir, cria. Seguro com vários workers ao mesmo tempo."""
    obj = db.scalar(select(modelo).filter_by(**filtro))
    if obj:
        return obj
    try:
        with db.begin_nested():
            obj = modelo(**filtro, **extra)
            db.add(obj)
        return obj
    except IntegrityError:
        return db.scalar(select(modelo).filter_by(**filtro))


def obter_ou_criar_especie(db: Session, nome: str) -> Especie:
    return obter_ou_criar(db, Especie, {"nome_cientifico": nome.strip()})


def recalcular_especie_final(foto: Foto) -> None:
    """Define a espécie final da foto.

    - Se a última revisão é uma confirmação, correção ou "não identificável", vale a revisão.
    - Se não há revisão (ou a última foi "restaurar"), vale o resultado mais recente do modelo.
    """
    revisao = foto.revisao
    if revisao and revisao.acao != AcaoRevisao.restaurou:
        foto.revisada = True
        foto.origem_especie = OrigemEspecie.revisao
        foto.especie_id = revisao.especie_id  # None quando "não identificável"
        return

    foto.revisada = False
    ident = foto.identificacao
    if ident and ident.identificada and ident.especie_id:
        foto.especie_id = ident.especie_id
        foto.origem_especie = OrigemEspecie.modelo
    else:
        foto.especie_id = None
        foto.origem_especie = None
