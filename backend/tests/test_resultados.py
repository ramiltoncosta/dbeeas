"""Testes da etapa 3: espécie final, revisões, resumo da coleta e filtros."""

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Revisao
from tests.conftest import auth, cadastrar, criar_coleta, enviar, imagem


@pytest.fixture
def token(client):
    return cadastrar(client)["access_token"]


def _enviar_varias(client, token, detector, especies_confiancas):
    """Envia uma foto para cada (espécie, confiança) e devolve (coleta, fotos)."""
    c = criar_coleta(client, token)
    fotos = []
    for i, (esp, conf) in enumerate(especies_confiancas):
        detector.especie, detector.confianca = esp, conf
        r = enviar(client, token, c["id"], (f"asa{i}.jpg", imagem(cor=(i * 20, 90, 60))))
        fotos.append(r.json()["aceitas"][0])
    return c, fotos


def revisar(client, token, foto_id, **dados):
    return client.post(f"/v1/fotos/{foto_id}/revisao", json=dados, headers=auth(token))


def test_especie_final_vem_do_modelo(client, token, detector):
    _, (foto,) = _enviar_varias(client, token, detector, [("Euglossa cognata", 0.9)])
    assert foto["especie"] == "Euglossa cognata"
    assert foto["origem_especie"] == "modelo"
    assert foto["revisada"] is False and foto["revisao"] is None


def test_confirmar(client, token, detector):
    _, (foto,) = _enviar_varias(client, token, detector, [("Euglossa cognata", 0.9)])
    r = revisar(client, token, foto["id"], acao="confirmar", observacao="  Conferido  na lupa ")
    assert r.status_code == 200, r.text
    f = r.json()
    assert f["especie"] == "Euglossa cognata"
    assert f["origem_especie"] == "revisao" and f["revisada"] is True
    assert f["revisao"]["acao"] == "confirmou"
    assert f["revisao"]["revisor"] == "Maria Silva"
    assert f["revisao"]["perfil_revisor"] == "pesquisador"
    assert f["revisao"]["observacao"] == "Conferido na lupa"


def test_corrigir_guarda_a_predicao_original(client, token, detector):
    _, (foto,) = _enviar_varias(client, token, detector, [("Euglossa cognata", 0.9)])
    r = revisar(client, token, foto["id"], acao="corrigir", especie="Euglossa modestior")
    f = r.json()
    assert f["especie"] == "Euglossa modestior"
    # A predição do modelo continua lá, intacta
    assert f["identificacao"]["especie"] == "Euglossa cognata"
    assert f["identificacao"]["confianca"] == 0.9
    with SessionLocal() as db:
        rev = db.scalar(select(Revisao))
        assert rev.identificacao_id is not None  # sabe o que o modelo dizia


def test_corrigir_para_especie_nova_cria_a_especie(client, token, detector):
    _, (foto,) = _enviar_varias(client, token, detector, [("Euglossa cognata", 0.9)])
    r = revisar(client, token, foto["id"], acao="corrigir", especie="Eulaema nigrita")
    assert r.json()["especie"] == "Eulaema nigrita"
    especies = client.get("/v1/especies", headers=auth(token)).json()
    nova = next(e for e in especies if e["nome_cientifico"] == "Eulaema nigrita")
    assert nova["reconhecida_pelo_modelo"] is False
    cognata = next(e for e in especies if e["nome_cientifico"] == "Euglossa cognata")
    assert cognata["reconhecida_pelo_modelo"] is True


def test_validacoes_da_revisao(client, token, detector):
    _, (foto,) = _enviar_varias(client, token, detector, [("Euglossa cognata", 0.2)])
    # Nada para confirmar (modelo não identificou)
    assert revisar(client, token, foto["id"], acao="confirmar").status_code == 409
    # Corrigir sem espécie
    assert revisar(client, token, foto["id"], acao="corrigir").status_code == 422
    # Nome fora do padrão científico
    r = revisar(client, token, foto["id"], acao="corrigir", especie="abelha verde")
    assert r.status_code == 422
    # Nada para restaurar
    assert revisar(client, token, foto["id"], acao="restaurar").status_code == 409


def test_nao_identificada_pode_ser_corrigida(client, token, detector):
    _, (foto,) = _enviar_varias(client, token, detector, [("Euglossa cognata", 0.2)])
    assert foto["especie"] is None
    r = revisar(client, token, foto["id"], acao="corrigir", especie="Euglossa intersecta")
    assert r.json()["especie"] == "Euglossa intersecta"


def test_nao_identificavel_e_restaurar(client, token, detector):
    _, (foto,) = _enviar_varias(client, token, detector, [("Euglossa cognata", 0.9)])
    r = revisar(client, token, foto["id"], acao="nao_identificavel", observacao="Asa rasgada")
    assert r.json()["especie"] is None and r.json()["revisada"] is True

    r = revisar(client, token, foto["id"], acao="restaurar")
    f = r.json()
    assert f["especie"] == "Euglossa cognata"
    assert f["origem_especie"] == "modelo" and f["revisada"] is False
    with SessionLocal() as db:
        assert len(db.scalars(select(Revisao)).all()) == 2  # histórico preservado


def test_reprocessar_nao_apaga_a_revisao(client, token, detector):
    _, (foto,) = _enviar_varias(client, token, detector, [("Euglossa cognata", 0.9)])
    revisar(client, token, foto["id"], acao="corrigir", especie="Euglossa modestior")

    # Novo modelo processa a foto de novo (ex.: depois de um retreino)
    from app.processamento import processar_foto

    with SessionLocal() as db:
        from app.models import Foto, StatusFoto

        db.get(Foto, foto["id"]).status = StatusFoto.na_fila
        db.commit()
    detector.versao, detector.especie = "teste-v2", "Euglossa pleosticta"
    processar_foto(foto["id"])

    f = client.get(f"/v1/fotos/{foto['id']}", headers=auth(token)).json()
    assert f["identificacao"]["especie"] == "Euglossa pleosticta"
    assert f["identificacao"]["versao_modelo"] == "teste-v2"
    assert f["especie"] == "Euglossa modestior"  # a revisão continua valendo


def test_resumo_da_coleta(client, token, detector):
    c, fotos = _enviar_varias(
        client,
        token,
        detector,
        [
            ("Euglossa cognata", 0.9),
            ("Euglossa cognata", 0.8),
            ("Euglossa cognata", 0.7),
            ("Euglossa modestior", 0.6),
            ("Euglossa cognata", 0.3),  # não identificada
        ],
    )
    # Uma "cognata" corrigida para "modestior"
    revisar(client, token, fotos[2]["id"], acao="corrigir", especie="Euglossa modestior")

    r = client.get(f"/v1/coletas/{c['id']}/resumo", headers=auth(token)).json()
    assert r["total"] == 5 and r["concluidas"] == 5
    assert r["identificadas"] == 4 and r["nao_identificadas"] == 1
    assert r["revisadas"] == 1
    esp = {e["nome"]: e for e in r["especies"]}
    assert esp["Euglossa cognata"]["quantidade"] == 2
    assert esp["Euglossa cognata"]["porcentagem"] == 50.0  # 2 de 4 identificadas
    assert esp["Euglossa cognata"]["confianca_media"] == pytest.approx(0.85)
    assert esp["Euglossa modestior"]["quantidade"] == 2
    assert esp["Euglossa modestior"]["revisadas"] == 1
    # Na foto corrigida o modelo disse outra espécie: não entra na média
    assert esp["Euglossa modestior"]["confianca_media"] == pytest.approx(0.6)
    assert r["especies"][0]["porcentagem"] + r["especies"][1]["porcentagem"] == 100

    # A contagem da coleta também usa a espécie final
    p = client.get(f"/v1/coletas/{c['id']}/progresso", headers=auth(token)).json()
    assert p["identificadas"] == 4 and p["nao_identificadas"] == 1


def test_resumo_de_coleta_vazia(client, token):
    c = criar_coleta(client, token)
    r = client.get(f"/v1/coletas/{c['id']}/resumo", headers=auth(token)).json()
    assert r["especies"] == [] and r["identificadas"] == 0


def test_filtros_de_fotos_por_grupo(client, token, detector):
    c, fotos = _enviar_varias(
        client,
        token,
        detector,
        [("Euglossa cognata", 0.9), ("Euglossa modestior", 0.9), ("Euglossa cognata", 0.2)],
    )
    revisar(client, token, fotos[0]["id"], acao="confirmar")
    url = f"/v1/coletas/{c['id']}/fotos"
    h = auth(token)

    resumo = client.get(f"/v1/coletas/{c['id']}/resumo", headers=h).json()
    id_cognata = next(e["id"] for e in resumo["especies"] if e["nome"] == "Euglossa cognata")
    r = client.get(url, params={"especie_id": id_cognata}, headers=h).json()
    assert [f["id"] for f in r["itens"]] == [fotos[0]["id"]]

    r = client.get(url, params={"grupo": "nao_identificadas"}, headers=h).json()
    assert [f["id"] for f in r["itens"]] == [fotos[2]["id"]]
    r = client.get(url, params={"grupo": "revisadas"}, headers=h).json()
    assert r["total"] == 1
    r = client.get(url, params={"grupo": "pendentes"}, headers=h).json()
    assert r["total"] == 0


def test_so_quem_tem_acesso_revisa(client, token, detector):
    _, (foto,) = _enviar_varias(client, token, detector, [("Euglossa cognata", 0.9)])
    outro = cadastrar(client, email="outro@exemplo.com")["access_token"]
    assert revisar(client, outro, foto["id"], acao="confirmar").status_code == 404


def test_admin_pode_revisar(client, token, detector, admin):
    _, (foto,) = _enviar_varias(client, token, detector, [("Euglossa cognata", 0.9)])
    r = revisar(client, admin, foto["id"], acao="corrigir", especie="Euglossa modestior")
    assert r.status_code == 200
    assert r.json()["revisao"]["perfil_revisor"] == "admin"


def test_revisao_antes_de_processar(client, token, detector, monkeypatch):
    monkeypatch.setattr("app.routers.coletas.enfileirar_fotos", lambda ids: None)
    c = criar_coleta(client, token)
    foto = enviar(client, token, c["id"], ("a.jpg", imagem())).json()["aceitas"][0]
    r = revisar(client, token, foto["id"], acao="corrigir", especie="Euglossa cognata")
    assert r.status_code == 409


def test_usuario_excluido_mantem_revisao_anonima(client, token, detector, admin):
    _, (foto,) = _enviar_varias(client, token, detector, [("Euglossa cognata", 0.9)])
    # O admin revisa a foto da Maria e depois o admin... não pode se excluir (único admin).
    # Então quem se exclui é um segundo admin.
    from sqlalchemy import update

    from app.models import Perfil, Usuario

    t2 = cadastrar(client, email="admin2@exemplo.com", nome="Admin 2")["access_token"]
    with SessionLocal() as db:
        db.execute(
            update(Usuario).where(Usuario.email == "admin2@exemplo.com").values(perfil=Perfil.admin)
        )
        db.commit()
    revisar(client, t2, foto["id"], acao="confirmar")
    r = client.request("DELETE", "/v1/eu", json={"senha": "abelha-123"}, headers=auth(t2))
    assert r.status_code == 204
    f = client.get(f"/v1/fotos/{foto['id']}", headers=auth(token)).json()
    assert f["revisada"] is True
    assert f["revisao"]["revisor"] is None  # quem revisou saiu, a revisão fica
