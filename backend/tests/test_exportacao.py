"""Testes da etapa 5: exportação em ZIP com planilha Darwin Core."""

import csv
import io
import zipfile
from datetime import timedelta

import pytest
from sqlalchemy import update

from app.db import SessionLocal
from app.models import Exportacao
from app.security import agora
from tests.conftest import auth, cadastrar, criar_coleta, enviar, imagem


@pytest.fixture
def token(client):
    return cadastrar(client)["access_token"]


def _coleta_com_fotos(client, token, detector):
    c = criar_coleta(
        client,
        token,
        nome="Mata do Baú – 2026",
        data_coleta="2026-03-10",
        municipio="Cuiabá",
        uf="MT",
        bioma="cerrado",
        coletor="Maria Silva",
        tipo_armadilha="Garrafa PET",
        isca_atrativa="Eucaliptol",
        local={"latitude": -15.6, "longitude": -56.1},
    )
    fotos = []
    for i, (esp, conf, gps) in enumerate(
        [
            ("Euglossa cognata", 0.91, (-15.61, -56.12)),
            ("Euglossa cognata", 0.88, None),
            ("Euglossa modestior", 0.77, None),
            ("Euglossa pleosticta", 0.2, None),  # não identificada
        ]
    ):
        detector.especie, detector.confianca = esp, conf
        r = enviar(client, token, c["id"], ("asa.jpg", imagem(cor=(i * 30, 90, 60), gps=gps)))
        assert r.status_code == 200, r.text
        fotos.append(r.json()["aceitas"][0])
    return c, fotos


def _exportar(client, token, coleta_id, tipo="original"):
    r = client.post(
        f"/v1/coletas/{coleta_id}/exportacoes", json={"tipo_imagem": tipo}, headers=auth(token)
    )
    assert r.status_code == 202, r.text
    return r.json()


def _baixar(client, exp):
    r = client.get(exp["url_download"])
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/zip"
    assert "attachment" in r.headers["content-disposition"]
    return zipfile.ZipFile(io.BytesIO(r.content))


def _csv(z):
    nome = next(n for n in z.namelist() if n.endswith("ocorrencias.csv"))
    texto = z.read(nome).decode("utf-8")
    assert texto.startswith("﻿")  # BOM: o Excel lê os acentos
    return list(csv.DictReader(io.StringIO(texto.lstrip("﻿"))))


def test_zip_por_especie_e_csv(client, token, detector):
    c, fotos = _coleta_com_fotos(client, token, detector)
    # Corrige a modestior para intersecta: o ZIP usa a espécie final
    client.post(
        f"/v1/fotos/{fotos[2]['id']}/revisao",
        json={"acao": "corrigir", "especie": "Euglossa intersecta", "observacao": "Tégula"},
        headers=auth(token),
    )
    exp = _exportar(client, token, c["id"])
    assert exp["status"] == "pronta" and exp["total_fotos"] == 4
    assert exp["tamanho_bytes"] > 0 and exp["expira_em"]

    z = _baixar(client, exp)
    nomes = sorted(z.namelist())
    raiz = "Mata_do_Bau_2026"
    assert f"{raiz}/LEIA-ME.txt" in nomes
    assert f"{raiz}/Euglossa_cognata/001_asa.jpg" in nomes
    assert f"{raiz}/Euglossa_cognata/002_asa.jpg" in nomes
    assert f"{raiz}/Euglossa_intersecta/001_asa.jpg" in nomes
    assert f"{raiz}/nao_identificadas/001_asa.jpg" in nomes
    assert not any("modestior" in n for n in nomes)
    # Original sem alteração
    assert z.read(f"{raiz}/Euglossa_cognata/001_asa.jpg")[:2] == b"\xff\xd8"

    linhas = _csv(z)
    assert len(linhas) == 4
    por_pasta = {(r["dbeeas_pasta"], r["associatedMedia"]): r for r in linhas}
    gps = por_pasta[("Euglossa_cognata", "Euglossa_cognata/001_asa.jpg")]
    assert gps["scientificName"] == "Euglossa cognata"
    assert gps["genus"] == "Euglossa" and gps["specificEpithet"] == "cognata"
    assert gps["taxonRank"] == "species" and gps["order"] == "Hymenoptera"
    assert gps["basisOfRecord"] == "MachineObservation"
    assert gps["decimalLatitude"] == "-15.610000"
    assert gps["georeferenceRemarks"] == "GPS da foto"
    assert gps["stateProvince"] == "Mato Grosso" and gps["municipality"] == "Cuiabá"
    assert gps["habitat"] == "Cerrado" and gps["countryCode"] == "BR"
    assert gps["samplingProtocol"] == "Armadilha: Garrafa PET; Isca: Eucaliptol"
    assert gps["recordedBy"] == "Maria Silva"
    assert gps["eventDate"] == "2026-03-10"
    assert gps["identifiedBy"] == "DBeeAS (modelo de IA teste-v1)"
    assert gps["dbeeas_confianca_modelo"] == "0.9100"
    assert gps["occurrenceID"] == f"urn:dbeeas:foto:{fotos[0]['id']}"

    sem_gps = por_pasta[("Euglossa_cognata", "Euglossa_cognata/002_asa.jpg")]
    assert sem_gps["decimalLatitude"] == "-15.600000"
    assert sem_gps["georeferenceRemarks"] == "Ponto geral da coleta"

    rev = por_pasta[("Euglossa_intersecta", "Euglossa_intersecta/001_asa.jpg")]
    assert rev["scientificName"] == "Euglossa intersecta"
    assert rev["basisOfRecord"] == "HumanObservation"
    assert rev["identifiedBy"] == "Maria Silva"
    assert rev["dbeeas_especie_modelo"] == "Euglossa modestior"
    assert rev["dbeeas_revisao"] == "corrigida"
    assert "Revisão: Tégula" in rev["identificationRemarks"]

    nao = por_pasta[("nao_identificadas", "nao_identificadas/001_asa.jpg")]
    assert nao["scientificName"] == ""
    assert nao["dbeeas_status"] == "concluida"

    leia = z.read(f"{raiz}/LEIA-ME.txt").decode()
    assert "Darwin Core" in leia and "Euglossa_cognata/  (2 foto(s))" in leia


def test_imagens_reduzidas(client, token, detector):
    c = criar_coleta(client, token)
    enviar(client, token, c["id"], ("grande.png", imagem(tamanho=(2400, 1800))))
    exp = _exportar(client, token, c["id"], "reduzida")
    z = _baixar(client, exp)
    (foto,) = [n for n in z.namelist() if "Euglossa" in n]
    assert foto.endswith("001_grande.jpg")
    from PIL import Image

    assert max(Image.open(io.BytesIO(z.read(foto))).size) == 1600


def test_fotos_com_erro_vao_para_nao_processadas(client, token, detector):
    from app.detector import ImagemRecusada

    c = criar_coleta(client, token)
    detector.erro = ImagemRecusada("ruim")
    enviar(client, token, c["id"], ("ruim.jpg", imagem()))
    z = _baixar(client, _exportar(client, token, c["id"]))
    assert any("/nao_processadas/001_ruim.jpg" in n for n in z.namelist())
    assert _csv(z)[0]["dbeeas_status"] == "erro"


def test_coleta_vazia(client, token):
    c = criar_coleta(client, token)
    r = client.post(f"/v1/coletas/{c['id']}/exportacoes", json={}, headers=auth(token))
    assert r.status_code == 400


def test_permissoes(client, token, detector, admin):
    c, _ = _coleta_com_fotos(client, token, detector)
    exp = _exportar(client, token, c["id"])
    outro = cadastrar(client, email="outro@exemplo.com")["access_token"]
    assert (
        client.post(f"/v1/coletas/{c['id']}/exportacoes", json={}, headers=auth(outro)).status_code
        == 404
    )
    assert client.get(f"/v1/exportacoes/{exp['id']}", headers=auth(outro)).status_code == 404
    assert client.get(f"/v1/coletas/{c['id']}/exportacoes", headers=auth(outro)).status_code == 404
    assert client.get(f"/v1/exportacoes/{exp['id']}", headers=auth(admin)).status_code == 200
    # Link adulterado não funciona
    assert client.get(exp["url_download"].replace("assinatura=", "assinatura=0")).status_code == 403


def test_nova_exportacao_substitui_a_anterior_e_expira(client, token, detector):
    from app.armazenamento import get_armazenamento

    c, _ = _coleta_com_fotos(client, token, detector)
    primeira = _exportar(client, token, c["id"])
    with SessionLocal() as db:
        chave = db.get(Exportacao, primeira["id"]).arquivo
    assert get_armazenamento().existe(chave)

    segunda = _exportar(client, token, c["id"])
    assert not get_armazenamento().existe(chave)
    lista = client.get(f"/v1/coletas/{c['id']}/exportacoes", headers=auth(token)).json()
    assert [e["id"] for e in lista] == [segunda["id"], primeira["id"]]
    assert lista[1]["status"] == "expirada" and lista[1]["url_download"] is None

    # Passou o prazo: some o link e, no próximo pedido, o arquivo é apagado
    with SessionLocal() as db:
        db.execute(update(Exportacao).values(expira_em=agora() - timedelta(minutes=1)))
        db.commit()
        chave2 = db.get(Exportacao, segunda["id"]).arquivo
    r = client.get(f"/v1/exportacoes/{segunda['id']}", headers=auth(token)).json()
    assert r["status"] == "expirada" and r["url_download"] is None
    _exportar(client, token, c["id"], "reduzida")
    assert not get_armazenamento().existe(chave2)


def test_excluir_coleta_apaga_o_zip(client, token, detector):
    from app.armazenamento import get_armazenamento

    c, _ = _coleta_com_fotos(client, token, detector)
    exp = _exportar(client, token, c["id"])
    with SessionLocal() as db:
        chave = db.get(Exportacao, exp["id"]).arquivo
    assert client.delete(f"/v1/coletas/{c['id']}", headers=auth(token)).status_code == 204
    assert not get_armazenamento().existe(chave)
