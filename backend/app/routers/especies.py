"""Lista de espécies (para escolher na correção de uma foto)."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import usuario_atual
from app.models import Especie, ModeloIA, Usuario
from app.schemas_coletas import EspecieOut

router = APIRouter(prefix="/especies", tags=["Espécies"])


@router.get("", response_model=list[EspecieOut])
def listar(_: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    """Todas as espécies conhecidas pelo sistema: as que o modelo reconhece e as que
    foram informadas por pesquisadores nas correções."""
    do_modelo: set[str] = set()
    for lista in db.scalars(select(ModeloIA.especies)):
        do_modelo.update(lista or [])
    return [
        EspecieOut(
            id=e.id,
            nome_cientifico=e.nome_cientifico,
            sensivel=e.sensivel,
            reconhecida_pelo_modelo=e.nome_cientifico in do_modelo,
        )
        for e in db.scalars(select(Especie).order_by(Especie.nome_cientifico))
    ]
