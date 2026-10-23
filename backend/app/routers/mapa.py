"""Mapa de ocorrências: onde cada espécie foi encontrada."""

import math
import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from geoalchemy2 import Geometry
from sqlalchemy import Date, cast, func, or_, select
from sqlalchemy.orm import Session

from app.armazenamento import url_assinada
from app.db import get_db
from app.deps import exigir_admin, pode_ver_localizacao_exata, usuario_atual
from app.models import Coleta, Especie, Foto, Perfil, StatusFoto, Usuario
from app.routers.especies import especie_out, nomes_do_modelo
from app.schemas_coletas import AdminEspecieIn, EspecieOut

router = APIRouter(tags=["Mapa"])

KM_POR_GRAU = 111.32


def aproximar(lat: float, lon: float, raio_km: float) -> tuple[float, float]:
    """Troca o ponto exato pelo centro de uma "célula" de cerca de `raio_km` de lado.

    A célula é sempre a mesma para o mesmo lugar: consultar várias vezes não ajuda
    a descobrir o ponto exato (diferente de somar um ruído aleatório a cada consulta).
    """
    passo_lat = raio_km / KM_POR_GRAU
    # A célula usa a latitude "arredondada" para que a largura não dependa do ponto exato
    lat_celula = math.floor(lat / passo_lat) * passo_lat + passo_lat / 2
    passo_lon = raio_km / (KM_POR_GRAU * max(math.cos(math.radians(lat_celula)), 0.01))
    lon_celula = math.floor(lon / passo_lon) * passo_lon + passo_lon / 2
    return round(lat_celula, 5), round(lon_celula, 5)


@router.get("/mapa/ocorrencias")
def ocorrencias(
    escopo: Literal["minhas", "todas"] = Query(
        "minhas",
        description="minhas: só as suas coletas · todas: inclui coletas públicas de outros",
    ),
    especie_id: int | None = None,
    coleta_id: uuid.UUID | None = None,
    inicio: date | None = Query(None, description="Data inicial (data da foto ou da coleta)"),
    fim: date | None = Query(None, description="Data final"),
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    """Ocorrências (fotos com espécie identificada e com localização) em GeoJSON.

    - A localização é a da foto (GPS ou marcada) ou, se não houver, o ponto da coleta.
    - Em ocorrências de outras pessoas não vão foto, nome da coleta nem quem coletou.
    - Espécies sensíveis aparecem com localização aproximada para quem não tem permissão
      (veja a regra em `pode_ver_localizacao_exata`).
    """
    ponto = cast(func.coalesce(Foto.local, Coleta.local), Geometry)
    data = func.coalesce(cast(Foto.data_captura, Date), Coleta.data_coleta)

    filtros = [
        Foto.status == StatusFoto.concluida,
        Foto.especie_id.is_not(None),
        func.coalesce(Foto.local, Coleta.local).is_not(None),
    ]
    if escopo == "minhas":
        filtros.append(Foto.usuario_id == usuario.id)
    elif usuario.perfil != Perfil.admin:
        filtros.append(or_(Foto.usuario_id == usuario.id, Coleta.publica_no_mapa.is_(True)))
    if especie_id is not None:
        filtros.append(Foto.especie_id == especie_id)
    if coleta_id is not None:
        filtros.append(Foto.coleta_id == coleta_id)
    if inicio:
        filtros.append(data >= inicio)
    if fim:
        filtros.append(data <= fim)

    linhas = db.execute(
        select(
            Foto.id,
            Foto.usuario_id,
            Foto.coleta_id,
            Foto.miniatura,
            Foto.revisada,
            Especie.id,
            Especie.nome_cientifico,
            Especie.sensivel,
            Especie.raio_ofuscacao_km,
            Coleta.nome,
            func.ST_Y(ponto),
            func.ST_X(ponto),
            data,
        )
        .join(Coleta, Coleta.id == Foto.coleta_id)
        .join(Especie, Especie.id == Foto.especie_id)
        .where(*filtros)
        .order_by(data.desc().nulls_last())
        .limit(20000)
    ).all()

    recursos = []
    for (
        foto_id, dono_id, col_id, miniatura, revisada, esp_id, esp_nome, sensivel, raio,
        col_nome, lat, lon, dia,
    ) in linhas:  # fmt: skip
        meu = dono_id == usuario.id or usuario.perfil == Perfil.admin
        aproximada = sensivel and not pode_ver_localizacao_exata(usuario, dono_id)
        if aproximada:
            lat, lon = aproximar(lat, lon, raio)
        propriedades = {
            "especie_id": esp_id,
            "especie": esp_nome,
            "data": dia.isoformat() if dia else None,
            "revisada": revisada,
            "aproximada": aproximada,
            "raio_km": raio if aproximada else None,
            "minha": dono_id == usuario.id,
        }
        if meu:
            propriedades |= {
                "foto_id": str(foto_id),
                "coleta_id": str(col_id),
                "coleta": col_nome,
                "url_miniatura": url_assinada(miniatura),
            }
        recursos.append(
            {
                "type": "Feature",
                # GeoJSON usa a ordem [longitude, latitude]
                "geometry": {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]},
                "properties": propriedades,
            }
        )
    return {"type": "FeatureCollection", "features": recursos}


@router.patch("/admin/especies/{especie_id}", response_model=EspecieOut, tags=["Administração"])
def atualizar_especie(
    especie_id: int,
    dados: AdminEspecieIn,
    _: Usuario = Depends(exigir_admin),
    db: Session = Depends(get_db),
):
    """Marca uma espécie como sensível (localização aproximada no mapa) e define o raio."""
    especie = db.get(Especie, especie_id)
    if especie is None:
        raise HTTPException(404, "Espécie não encontrada.")
    if dados.sensivel is not None:
        especie.sensivel = dados.sensivel
    if dados.raio_ofuscacao_km is not None:
        especie.raio_ofuscacao_km = dados.raio_ofuscacao_km
    db.commit()
    return especie_out(especie, nomes_do_modelo(db))
