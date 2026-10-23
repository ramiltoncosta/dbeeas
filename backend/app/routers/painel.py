"""Painel: resumo das coletas e fotos do usuário (e da plataforma, para o administrador)."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import usuario_atual
from app.models import (
    Coleta,
    Especie,
    Foto,
    MensagemContato,
    Perfil,
    StatusFoto,
    Usuario,
)
from app.routers.coletas import contar_fotos, para_revisar
from app.schemas_coletas import ColetaOut
from app.schemas_especies import (
    ColetaParaRevisar,
    EspeciePainel,
    Painel,
    PlataformaPainel,
    TotaisPainel,
)
from app.security import agora

router = APIRouter(prefix="/painel", tags=["Painel"])


def _soma(cond):
    return func.coalesce(func.sum(case((cond, 1), else_=0)), 0)


def _inicio_do_dia_e_mes() -> tuple[datetime, datetime]:
    fuso = ZoneInfo(get_settings().fuso_horario_padrao)
    hoje = datetime.now(fuso).replace(hour=0, minute=0, second=0, microsecond=0)
    return hoje, hoje.replace(day=1)


@router.get("", response_model=Painel)
def painel(usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    s = get_settings()
    hoje, inicio_mes = _inicio_do_dia_e_mes()
    minhas = Foto.usuario_id == usuario.id
    concluida = Foto.status == StatusFoto.concluida

    t = db.execute(
        select(
            func.count(Foto.id),
            _soma(concluida & Foto.especie_id.is_not(None)),
            _soma(concluida & Foto.especie_id.is_(None)),
            _soma(Foto.status.in_([StatusFoto.na_fila, StatusFoto.processando])),
            _soma(Foto.status == StatusFoto.erro),
            _soma(Foto.revisada.is_(True)),
            func.count(func.distinct(Foto.especie_id)),
            _soma(Foto.enviada_em >= inicio_mes),
        ).where(minhas)
    ).one()
    n_coletas = db.scalar(
        select(func.count()).select_from(Coleta).where(Coleta.usuario_id == usuario.id)
    )
    totais = TotaisPainel(
        coletas=n_coletas,
        fotos=t[0],
        identificadas=t[1],
        nao_identificadas=t[2],
        em_processamento=t[3],
        com_erro=t[4],
        revisadas=t[5],
        especies=t[6],
        fotos_mes=t[7],
    )

    linhas = db.execute(
        select(
            Especie.id,
            Especie.nome_cientifico,
            func.count(Foto.id),
            func.count(func.distinct(Foto.coleta_id)),
        )
        .join(Foto, Foto.especie_id == Especie.id)
        .where(minhas, concluida)
        .group_by(Especie.id)
        .order_by(func.count(Foto.id).desc(), Especie.nome_cientifico)
    ).all()
    especies = [
        EspeciePainel(
            id=i,
            nome=nome,
            quantidade=n,
            porcentagem=round(n * 100 / totais.identificadas, 1) if totais.identificadas else 0,
            coletas=nc,
        )
        for i, nome, n, nc in linhas
    ]

    recentes = db.scalars(
        select(Coleta)
        .where(Coleta.usuario_id == usuario.id)
        .order_by(Coleta.criado_em.desc())
        .limit(5)
    ).all()
    contagens = contar_fotos(db, [c.id for c in recentes])

    baixa = minhas & para_revisar()
    por_coleta = db.execute(
        select(Coleta.id, Coleta.nome, func.count(Foto.id))
        .join(Foto, Foto.coleta_id == Coleta.id)
        .where(baixa)
        .group_by(Coleta.id)
        .order_by(func.count(Foto.id).desc())
    ).all()

    plataforma = None
    if usuario.perfil == Perfil.admin:
        p = db.execute(
            select(
                func.count(Foto.id),
                _soma(Foto.enviada_em >= hoje),
                _soma(Foto.status.in_([StatusFoto.na_fila, StatusFoto.processando])),
                _soma(Foto.status == StatusFoto.erro),
            )
        ).one()
        plataforma = PlataformaPainel(
            usuarios=db.scalar(select(func.count()).select_from(Usuario)),
            usuarios_novos_30d=db.scalar(
                select(func.count())
                .select_from(Usuario)
                .where(Usuario.criado_em >= agora() - timedelta(days=30))
            ),
            coletas=db.scalar(select(func.count()).select_from(Coleta)),
            fotos=p[0],
            fotos_hoje=p[1],
            na_fila=p[2],
            com_erro=p[3],
            mensagens_nao_respondidas=db.scalar(
                select(func.count())
                .select_from(MensagemContato)
                .where(MensagemContato.respondida.is_(False))
            ),
        )

    return Painel(
        totais=totais,
        especies=especies,
        ultimas_coletas=[ColetaOut.de(c, contagens.get(c.id)) for c in recentes],
        para_revisar=sum(n for _, _, n in por_coleta),
        para_revisar_coletas=[
            ColetaParaRevisar(id=i, nome=nome, fotos=n) for i, nome, n in por_coleta[:5]
        ],
        limite_confianca_revisao=s.confianca_revisao,
        plataforma=plataforma,
    )
