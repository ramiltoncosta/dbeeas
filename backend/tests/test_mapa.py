"""Testes do mapa de ocorrências e da proteção de espécies sensíveis."""

import math

import pytest
from sqlalchemy import update

from app.db import SessionLocal
from app.models import Especie, Perfil, Usuario
from app.routers.mapa import aproximar
from tests.conftest import auth, cadastrar, criar_coleta, enviar, imagem

# Pontos em Cuiabá e Chapada dos Guimarães
CUIABA = (-15.6014, -56.0979)
CHAPADA = (-15.4609, -55.7499)


def _distancia_km(a, b):
    lat = math.radians((a[0] + b[0]) / 2)
    dy = (a[0] - b[0]) * 111.32
    dx = (a[1] - b[1]) * 111.32 * math.cos(lat)
    return math.hypot(dx, dy)


def _usuario(client, email, perfil="pesquisador"):
    t = cadastrar(client, email=email, nome=email.split("@")[0])["access_token"]
    client.cookies.clear()
    if perfil != "pesquisador":
        with SessionLocal() as db:
            db.execute(update(Usuario).where(Usuario.email == email).values(perfil=Perfil(perfil)))
            db.commit()
    return t


def _ocorrencias(client, token, **params):
    r = client.get("/v1/mapa/ocorrencias", params=params, headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()["features"]


@pytest.fixture
def cenario(client, detector):
    """Maria tem duas fotos (uma de cada espécie) em Cuiabá; Euglossa cognata é sensível."""
    maria = _usuario(client, "maria@exemplo.com")
    c = criar_coleta(client, maria, nome="Coleta da Maria", data_coleta="2026-10-01")
    detector.especie = "Euglossa cognata"
    enviar(client, maria, c["id"], ("a.jpg", imagem(gps=CUIABA)))
    detector.especie = "Euglossa modestior"
    enviar(client, maria, c["id"], ("b.jpg", imagem(cor=(1, 2, 3), gps=CUIABA)))
    with SessionLocal() as db:
        db.execute(
            update(Especie)
            .where(Especie.nome_cientifico == "Euglossa cognata")
            .values(sensivel=True, raio_ofuscacao_km=10)
        )
        db.commit()
    return {"maria": maria, "coleta": c}


def test_aproximar_e_deterministico_e_proximo():
    a = aproximar(*CUIABA, 10)
    assert a == aproximar(*CUIABA, 10)  # sempre a mesma célula
    assert a != CUIABA
    assert _distancia_km(a, CUIABA) < 10  # no máximo meia diagonal da célula (~7 km)
    # Pontos vizinhos caem na mesma célula: não dá para "triangular" o ponto exato
    vizinho = (CUIABA[0] + 0.001, CUIABA[1] + 0.001)
    assert aproximar(*vizinho, 10) == a


def test_dono_ve_suas_ocorrencias_exatas_com_detalhes(client, cenario):
    feats = _ocorrencias(client, cenario["maria"])
    assert len(feats) == 2
    for f in feats:
        lon, lat = f["geometry"]["coordinates"]
        assert (lat, lon) == pytest.approx(CUIABA, abs=1e-4)
        assert f["properties"]["aproximada"] is False
        assert f["properties"]["coleta"] == "Coleta da Maria"
        assert f["properties"]["url_miniatura"]
        assert f["properties"]["data"] == "2026-10-01"


def test_escopo_minhas_nao_mostra_dos_outros(client, cenario):
    joao = _usuario(client, "joao@exemplo.com", "estudante")
    assert _ocorrencias(client, joao) == []


def test_estudante_ve_especie_sensivel_aproximada_e_sem_detalhes(client, cenario):
    joao = _usuario(client, "joao@exemplo.com", "estudante")
    feats = {f["properties"]["especie"]: f for f in _ocorrencias(client, joao, escopo="todas")}
    sensivel = feats["Euglossa cognata"]
    lon, lat = sensivel["geometry"]["coordinates"]
    assert sensivel["properties"]["aproximada"] is True
    assert sensivel["properties"]["raio_km"] == 10
    assert (lat, lon) != pytest.approx(CUIABA, abs=1e-3)
    # Sem foto, sem nome da coleta, sem ids
    for chave in ("url_miniatura", "coleta", "foto_id", "coleta_id"):
        assert chave not in sensivel["properties"]
    # Espécie não sensível: ponto exato, mas também sem detalhes
    comum = feats["Euglossa modestior"]
    assert comum["properties"]["aproximada"] is False
    assert "url_miniatura" not in comum["properties"]


def test_orgao_publico_tambem_ve_aproximada(client, cenario):
    orgao = _usuario(client, "sema@exemplo.com", "orgao_publico")
    feats = _ocorrencias(client, orgao, escopo="todas")
    assert any(f["properties"]["aproximada"] for f in feats)


def test_pesquisador_ve_exata(client, cenario):
    pesq = _usuario(client, "pesq@exemplo.com")
    feats = _ocorrencias(client, pesq, escopo="todas")
    assert all(not f["properties"]["aproximada"] for f in feats)
    assert all("url_miniatura" not in f["properties"] for f in feats)  # mas sem fotos


def test_admin_ve_tudo(client, cenario, admin):
    feats = _ocorrencias(client, admin, escopo="todas")
    assert len(feats) == 2
    assert all(
        not f["properties"]["aproximada"] and f["properties"]["url_miniatura"] for f in feats
    )


def test_coleta_privada_nao_aparece_para_outros(client, cenario):
    r = client.patch(
        f"/v1/coletas/{cenario['coleta']['id']}",
        json={"publica_no_mapa": False},
        headers=auth(cenario["maria"]),
    )
    assert r.json()["publica_no_mapa"] is False
    joao = _usuario(client, "joao@exemplo.com", "estudante")
    assert _ocorrencias(client, joao, escopo="todas") == []
    assert len(_ocorrencias(client, cenario["maria"], escopo="todas")) == 2  # a dona continua vendo


def test_filtros(client, cenario, detector):
    maria = cenario["maria"]
    c2 = criar_coleta(client, maria, nome="Chapada", data_coleta="2026-06-15")
    detector.especie = "Euglossa modestior"
    enviar(client, maria, c2["id"], ("c.jpg", imagem(cor=(9, 9, 9), gps=CHAPADA)))

    todas = _ocorrencias(client, maria)
    assert len(todas) == 3
    id_mod = next(
        f["properties"]["especie_id"]
        for f in todas
        if f["properties"]["especie"] == "Euglossa modestior"
    )
    assert len(_ocorrencias(client, maria, especie_id=id_mod)) == 2
    assert len(_ocorrencias(client, maria, coleta_id=c2["id"])) == 1
    assert len(_ocorrencias(client, maria, inicio="2026-09-01")) == 2
    assert len(_ocorrencias(client, maria, fim="2026-07-01")) == 1


def test_foto_sem_gps_usa_o_ponto_da_coleta(client, detector):
    t = _usuario(client, "ana@exemplo.com")
    c = criar_coleta(client, t, local={"latitude": CHAPADA[0], "longitude": CHAPADA[1]})
    enviar(client, t, c["id"], ("sem-gps.jpg", imagem()))
    (f,) = _ocorrencias(client, t)
    lon, lat = f["geometry"]["coordinates"]
    assert (lat, lon) == pytest.approx(CHAPADA, abs=1e-5)


def test_sem_localizacao_nao_aparece(client, detector):
    t = _usuario(client, "ana@exemplo.com")
    c = criar_coleta(client, t)
    enviar(client, t, c["id"], ("sem-gps.jpg", imagem()))
    assert _ocorrencias(client, t) == []


def test_nao_identificadas_nao_aparecem(client, detector):
    detector.confianca = 0.2
    t = _usuario(client, "ana@exemplo.com")
    c = criar_coleta(client, t)
    enviar(client, t, c["id"], ("a.jpg", imagem(gps=CUIABA)))
    assert _ocorrencias(client, t) == []


def test_admin_marca_especie_sensivel(client, cenario, admin):
    especies = client.get("/v1/especies", headers=auth(admin)).json()
    mod = next(e for e in especies if e["nome_cientifico"] == "Euglossa modestior")
    r = client.patch(
        f"/v1/admin/especies/{mod['id']}",
        json={"sensivel": True, "raio_ofuscacao_km": 25},
        headers=auth(admin),
    )
    assert r.status_code == 200
    assert r.json()["sensivel"] is True and r.json()["raio_ofuscacao_km"] == 25
    # Usuário comum não pode
    r = client.patch(
        f"/v1/admin/especies/{mod['id']}", json={"sensivel": False}, headers=auth(cenario["maria"])
    )
    assert r.status_code == 403
