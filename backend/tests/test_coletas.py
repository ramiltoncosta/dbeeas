"""Testes de coletas, envio de fotos, fila de processamento e arquivos."""

import io
from datetime import UTC, datetime, timedelta

import pytest
from PIL import Image
from sqlalchemy import func, select, update

from app.armazenamento import get_armazenamento
from app.db import SessionLocal
from app.imagens import ImagemInvalida, analisar
from app.models import Especie, Foto, ModeloIA
from tests.conftest import auth, cadastrar, criar_coleta, enviar, imagem

# Cuiabá (aprox.)
LAT, LON = -15.6014, -56.0979


@pytest.fixture
def token(client):
    return cadastrar(client)["access_token"]


# --- Leitura das imagens -----------------------------------------------------


def test_le_gps_e_data_do_exif():
    info = analisar(imagem(gps=(LAT, LON), data="2026:10:20 09:30:00"))
    assert info.tipo_mime == "image/jpeg"
    assert info.latitude == pytest.approx(LAT, abs=1e-4)
    assert info.longitude == pytest.approx(LON, abs=1e-4)
    # Sem fuso no EXIF: usa o fuso padrão (America/Sao_Paulo, -03:00)
    assert info.data_captura.astimezone(UTC) == datetime(2026, 10, 20, 12, 30, tzinfo=UTC)


def test_foto_sem_exif():
    info = analisar(imagem(formato="PNG"))
    assert info.tipo_mime == "image/png"
    assert info.latitude is None and info.data_captura is None


def test_foto_deitada_tem_largura_e_altura_trocadas():
    info = analisar(imagem(tamanho=(64, 48), orientacao=6))
    assert (info.largura, info.altura) == (48, 64)


def test_rejeita_arquivo_que_nao_e_imagem():
    with pytest.raises(ImagemInvalida):
        analisar(b"%PDF-1.4 isto nao e uma imagem")


def test_rejeita_formato_nao_aceito():
    saida = io.BytesIO()
    Image.new("RGB", (10, 10)).save(saida, format="GIF")
    with pytest.raises(ImagemInvalida):
        analisar(saida.getvalue())


# --- Coletas -----------------------------------------------------------------


def test_criar_e_editar_coleta(client, token):
    c = criar_coleta(
        client,
        token,
        nome="  Fazenda Boa Vista  ",
        data_coleta="2026-10-20",
        municipio="Cuiabá",
        uf="mt",
        coletor="Ramilton",
        tipo_armadilha="Armadilha de garrafa PET",
        isca_atrativa="Eucaliptol",
        bioma="cerrado",
        local={"latitude": LAT, "longitude": LON},
    )
    assert c["nome"] == "Fazenda Boa Vista"
    assert c["uf"] == "MT"
    assert c["local"]["latitude"] == pytest.approx(LAT)
    assert c["fotos"]["total"] == 0

    r = client.patch(
        f"/v1/coletas/{c['id']}",
        json={"isca_atrativa": "Salicilato de metila", "local": None},
        headers=auth(token),
    )
    assert r.status_code == 200
    assert r.json()["isca_atrativa"] == "Salicilato de metila"
    assert r.json()["local"] is None
    assert r.json()["bioma"] == "cerrado"  # campos não enviados não mudam


def test_validacoes_da_coleta(client, token):
    h = auth(token)
    assert client.post("/v1/coletas", json={"nome": ""}, headers=h).status_code == 422
    assert client.post("/v1/coletas", json={"nome": "x", "uf": "XX"}, headers=h).status_code == 422
    amanha = (datetime.now() + timedelta(days=2)).date().isoformat()
    r = client.post("/v1/coletas", json={"nome": "x", "data_coleta": amanha}, headers=h)
    assert r.status_code == 422
    r = client.post("/v1/coletas", json={"nome": "x", "local": {"latitude": 99, "longitude": 0}}, headers=h)
    assert r.status_code == 422


def test_listar_coletas_so_mostra_as_minhas(client, token):
    criar_coleta(client, token, nome="Minha")
    outro = cadastrar(client, email="outro@exemplo.com")["access_token"]
    c_outro = criar_coleta(client, outro, nome="Do outro")

    r = client.get("/v1/coletas", headers=auth(token))
    assert [c["nome"] for c in r.json()["itens"]] == ["Minha"]
    # Coleta de outra pessoa: 404 (não revela que existe)
    assert client.get(f"/v1/coletas/{c_outro['id']}", headers=auth(token)).status_code == 404
    r = client.patch(f"/v1/coletas/{c_outro['id']}", json={"nome": "x"}, headers=auth(token))
    assert r.status_code == 404


def test_admin_ve_coletas_de_todos(client, token, admin):
    criar_coleta(client, token, nome="Do pesquisador")
    r = client.get("/v1/coletas", params={"todas": True}, headers=auth(admin))
    assert r.json()["total"] == 1
    # Sem "todas", nem o admin vê as dos outros na lista
    assert client.get("/v1/coletas", headers=auth(admin)).json()["total"] == 0


# --- Envio e processamento ---------------------------------------------------


def test_envio_em_lote_processa_e_identifica(client, token, detector):
    c = criar_coleta(client, token)
    r = enviar(
        client,
        token,
        c["id"],
        ("asa1.jpg", imagem(gps=(LAT, LON), data="2026:10:20 09:30:00")),
        ("asa2.jpg", imagem(cor=(10, 20, 30))),
    )
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["rejeitadas"] == []
    assert len(corpo["aceitas"]) == 2

    foto1 = next(f for f in corpo["aceitas"] if f["nome_original"] == "asa1.jpg")
    assert foto1["status"] == "concluida"
    assert foto1["origem_local"] == "exif"
    assert foto1["local"]["latitude"] == pytest.approx(LAT, abs=1e-4)
    assert foto1["identificacao"]["especie"] == "Euglossa cognata"
    assert foto1["identificacao"]["versao_modelo"] == "teste-v1"
    assert foto1["identificacao"]["deteccoes"][0]["caixa"]["x2"] == 30.0
    assert foto1["url_miniatura"].startswith("/v1/arquivos/")

    p = client.get(f"/v1/coletas/{c['id']}/progresso", headers=auth(token)).json()
    assert p == {
        "total": 2, "na_fila": 0, "processando": 0, "concluidas": 2, "erro": 0,
        "identificadas": 2, "nao_identificadas": 0,
    }  # fmt: skip

    # Espécies e modelo foram cadastrados automaticamente
    with SessionLocal() as db:
        nomes = set(db.scalars(select(Especie.nome_cientifico)))
        assert nomes == {"Euglossa cognata", "Euglossa modestior"}
        assert db.scalar(select(ModeloIA.versao)) == "teste-v1"


def test_foto_nao_identificada(client, token, detector):
    detector.confianca = 0.2
    c = criar_coleta(client, token)
    foto = enviar(client, token, c["id"], ("asa.jpg", imagem())).json()["aceitas"][0]
    assert foto["status"] == "concluida"
    assert foto["identificacao"]["identificada"] is False
    assert foto["identificacao"]["especie"] is None
    p = client.get(f"/v1/coletas/{c['id']}/progresso", headers=auth(token)).json()
    assert p["nao_identificadas"] == 1 and p["identificadas"] == 0


def test_rejeita_invalidas_e_repetidas(client, token, detector):
    c = criar_coleta(client, token)
    foto = imagem()
    r = enviar(
        client,
        token,
        c["id"],
        ("boa.jpg", foto),
        ("repetida.jpg", foto),
        ("falsa.jpg", b"nao sou imagem"),
    )
    corpo = r.json()
    assert [f["nome_original"] for f in corpo["aceitas"]] == ["boa.jpg"]
    motivos = {x["arquivo"]: x["motivo"] for x in corpo["rejeitadas"]}
    assert "já está na coleta" in motivos["repetida.jpg"]
    assert "não é uma imagem" in motivos["falsa.jpg"]

    # Enviar de novo depois também é recusado
    r = enviar(client, token, c["id"], ("boa-de-novo.jpg", foto))
    assert r.json()["aceitas"] == []


def test_limite_de_tamanho(client, token, detector, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "upload_max_mb", 0)
    c = criar_coleta(client, token)
    r = enviar(client, token, c["id"], ("grande.jpg", imagem()))
    assert "Maior que" in r.json()["rejeitadas"][0]["motivo"]


def test_falha_temporaria_tenta_de_novo(client, token, detector):
    detector.falhas_temporarias = 2  # cai duas vezes, funciona na terceira
    c = criar_coleta(client, token)
    foto = enviar(client, token, c["id"], ("asa.jpg", imagem())).json()["aceitas"][0]
    assert foto["status"] == "concluida"
    assert foto["tentativas"] == 3


def test_detector_fora_do_ar_marca_erro_e_permite_reprocessar(client, token, detector):
    detector.falhas_temporarias = 99
    c = criar_coleta(client, token)
    foto = enviar(client, token, c["id"], ("asa.jpg", imagem())).json()["aceitas"][0]
    assert foto["status"] == "erro"
    assert foto["tentativas"] == 3
    assert foto["url_miniatura"]  # a miniatura foi gerada mesmo assim

    detector.falhas_temporarias = 0
    r = client.post(f"/v1/fotos/{foto['id']}/reprocessar", headers=auth(token))
    assert r.status_code == 200
    assert r.json()["status"] == "concluida"

    # Foto concluída não precisa de reprocessamento
    r = client.post(f"/v1/fotos/{foto['id']}/reprocessar", headers=auth(token))
    assert r.status_code == 409


def test_imagem_recusada_pelo_detector_nao_tenta_de_novo(client, token, detector):
    from app.detector import ImagemRecusada

    detector.erro = ImagemRecusada("Imagem recusada pelo detector: formato")
    c = criar_coleta(client, token)
    foto = enviar(client, token, c["id"], ("asa.jpg", imagem())).json()["aceitas"][0]
    assert foto["status"] == "erro"
    assert detector.chamadas == 1


def test_fila_fora_do_ar_nao_perde_as_fotos(client, token, detector, monkeypatch):
    def quebrada(ids):
        raise ConnectionError("redis fora do ar")

    monkeypatch.setattr("app.routers.coletas.enfileirar_fotos", quebrada)
    c = criar_coleta(client, token)
    foto = enviar(client, token, c["id"], ("asa.jpg", imagem())).json()["aceitas"][0]
    assert foto["status"] == "na_fila"


# --- Fotos -------------------------------------------------------------------


def test_marcar_local_e_sexo(client, token, detector):
    c = criar_coleta(client, token)
    foto = enviar(client, token, c["id"], ("asa.jpg", imagem())).json()["aceitas"][0]
    assert foto["local"] is None

    r = client.patch(
        f"/v1/fotos/{foto['id']}",
        json={"local": {"latitude": LAT, "longitude": LON}, "sexo": "macho"},
        headers=auth(token),
    )
    assert r.json()["origem_local"] == "manual"
    assert r.json()["sexo"] == "macho"

    r = client.patch(f"/v1/fotos/{foto['id']}", json={"local": None}, headers=auth(token))
    assert r.json()["local"] is None and r.json()["sexo"] == "macho"


def test_listar_fotos_com_filtro(client, token, detector):
    c = criar_coleta(client, token)
    enviar(client, token, c["id"], ("a.jpg", imagem()), ("b.jpg", imagem(cor=(1, 2, 3))))
    r = client.get(f"/v1/coletas/{c['id']}/fotos", headers=auth(token))
    assert r.json()["total"] == 2
    r = client.get(f"/v1/coletas/{c['id']}/fotos", params={"status": "erro"}, headers=auth(token))
    assert r.json()["total"] == 0


def test_links_assinados_das_imagens(client, token, detector):
    c = criar_coleta(client, token)
    foto = enviar(client, token, c["id"], ("asa.jpg", imagem())).json()["aceitas"][0]

    r = client.get(foto["url_miniatura"])  # sem token de login: o link basta
    assert r.status_code == 200
    assert Image.open(io.BytesIO(r.content)).format == "JPEG"

    adulterado = foto["url_original"].replace("assinatura=", "assinatura=0")
    assert client.get(adulterado).status_code == 403
    outra_chave = foto["url_original"].replace(".jpg?", "_mini.jpg?")
    assert client.get(outra_chave).status_code == 403


def test_excluir_foto_e_coleta_apaga_arquivos(client, token, detector):
    arm = get_armazenamento()
    c = criar_coleta(client, token)
    fotos = enviar(client, token, c["id"], ("a.jpg", imagem()), ("b.jpg", imagem(cor=(9, 9, 9))))
    fotos = fotos.json()["aceitas"]
    with SessionLocal() as db:
        chaves = [x for f in db.scalars(select(Foto)) for x in (f.arquivo, f.miniatura, f.media)]
    assert all(arm.existe(k) for k in chaves)

    assert client.delete(f"/v1/fotos/{fotos[0]['id']}", headers=auth(token)).status_code == 204
    assert client.delete(f"/v1/coletas/{c['id']}", headers=auth(token)).status_code == 204
    assert not any(arm.existe(k) for k in chaves)
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Foto)) == 0


def test_lgpd_exporta_coletas_e_exclusao_apaga_fotos(client, token, detector):
    arm = get_armazenamento()
    c = criar_coleta(client, token, nome="Para exportar")
    enviar(client, token, c["id"], ("a.jpg", imagem()))
    dados = client.get("/v1/eu/dados", headers=auth(token)).json()
    assert dados["coletas"][0]["nome"] == "Para exportar"
    assert dados["coletas"][0]["fotos"][0]["nome_original"] == "a.jpg"

    with SessionLocal() as db:
        chave = db.scalar(select(Foto.arquivo))
    r = client.request("DELETE", "/v1/eu", json={"senha": "abelha-123"}, headers=auth(token))
    assert r.status_code == 204
    assert not arm.existe(chave)


def test_foto_travada_pode_ser_reprocessada(client, token, detector, monkeypatch):
    monkeypatch.setattr("app.routers.coletas.enfileirar_fotos", lambda ids: None)
    c = criar_coleta(client, token)
    foto = enviar(client, token, c["id"], ("asa.jpg", imagem())).json()["aceitas"][0]
    url = f"/v1/fotos/{foto['id']}/reprocessar"
    assert client.post(url, headers=auth(token)).status_code == 409  # acabou de entrar na fila

    with SessionLocal() as db:
        db.execute(update(Foto).values(enviada_em=datetime.now(UTC) - timedelta(hours=1)))
        db.commit()
    r = client.post(url, headers=auth(token))
    assert r.json()["status"] == "concluida"


# --- Identificação rápida ----------------------------------------------------


def test_identificacao_rapida(client, token, detector):
    r = client.post(
        "/v1/identificar",
        files={"arquivo": ("asa.jpg", imagem(), "image/jpeg")},
        headers=auth(token),
    )
    assert r.status_code == 200
    assert r.json()["especie"] == "Euglossa cognata"
    assert r.json()["imagem_anotada"]


def test_identificacao_rapida_exige_login_e_imagem_valida(client, token, detector):
    arquivo = {"arquivo": ("asa.jpg", imagem(), "image/jpeg")}
    assert client.post("/v1/identificar", files=arquivo).status_code == 401
    r = client.post(
        "/v1/identificar",
        files={"arquivo": ("x.jpg", b"nada", "image/jpeg")},
        headers=auth(token),
    )
    assert r.status_code == 415


def test_identificacao_rapida_com_detector_fora_do_ar(client, token, detector):
    detector.falhas_temporarias = 1
    r = client.post(
        "/v1/identificar",
        files={"arquivo": ("asa.jpg", imagem(), "image/jpeg")},
        headers=auth(token),
    )
    assert r.status_code == 503
