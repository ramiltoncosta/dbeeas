"""Testes da etapa 6: painel, fichas das espécies, catálogo público e contato."""

import pytest

from tests.conftest import auth, cadastrar, criar_coleta, enviar, imagem


@pytest.fixture
def token(client):
    return cadastrar(client)["access_token"]


def _enviar(client, token, detector, coleta_id, especie, conf, i=0):
    detector.especie, detector.confianca = especie, conf
    r = enviar(client, token, coleta_id, (f"a{i}.jpg", imagem(cor=(i * 25 % 255, 80, 40))))
    assert r.status_code == 200, r.text
    return r.json()["aceitas"][0]


def _id_especie(client, token, nome):
    return next(
        e["id"]
        for e in client.get("/v1/especies", headers=auth(token)).json()
        if e["nome_cientifico"] == nome
    )


# --- Painel ---------------------------------------------------------------------


def test_painel_vazio(client, token):
    r = client.get("/v1/painel", headers=auth(token))
    assert r.status_code == 200
    p = r.json()
    assert p["totais"]["coletas"] == 0 and p["totais"]["fotos"] == 0
    assert p["especies"] == [] and p["ultimas_coletas"] == []
    assert p["plataforma"] is None


def test_painel_com_dados(client, token, detector):
    c1 = criar_coleta(client, token, nome="Primeira")
    c2 = criar_coleta(client, token, nome="Segunda")
    _enviar(client, token, detector, c1["id"], "Euglossa cognata", 0.95, 1)
    _enviar(client, token, detector, c1["id"], "Euglossa cognata", 0.6, 2)  # baixa
    _enviar(client, token, detector, c2["id"], "Euglossa cognata", 0.9, 3)
    f = _enviar(client, token, detector, c2["id"], "Euglossa modestior", 0.55, 4)  # baixa
    _enviar(client, token, detector, c2["id"], "Euglossa modestior", 0.3, 5)  # não identificada
    # Revisada: sai da lista "para revisar"
    client.post(f"/v1/fotos/{f['id']}/revisao", json={"acao": "confirmar"}, headers=auth(token))

    # Dados de outra pessoa não entram
    outro = cadastrar(client, email="outro@exemplo.com")["access_token"]
    c3 = criar_coleta(client, outro)
    _enviar(client, outro, detector, c3["id"], "Euglossa intersecta", 0.9, 6)

    p = client.get("/v1/painel", headers=auth(token)).json()
    t = p["totais"]
    assert t == {
        "coletas": 2,
        "fotos": 5,
        "identificadas": 4,
        "nao_identificadas": 1,
        "em_processamento": 0,
        "com_erro": 0,
        "revisadas": 1,
        "especies": 2,
        "fotos_mes": 5,
    }
    assert [
        (e["nome"], e["quantidade"], e["porcentagem"], e["coletas"]) for e in p["especies"]
    ] == [
        ("Euglossa cognata", 3, 75.0, 2),
        ("Euglossa modestior", 1, 25.0, 1),
    ]
    assert [c["nome"] for c in p["ultimas_coletas"]] == ["Segunda", "Primeira"]
    assert p["para_revisar"] == 1
    assert p["para_revisar_coletas"] == [{"id": c1["id"], "nome": "Primeira", "fotos": 1}]

    # O mesmo filtro funciona na coleta
    r = client.get(f"/v1/coletas/{c1['id']}/fotos?grupo=para_revisar", headers=auth(token))
    assert r.json()["total"] == 1
    assert (
        client.get(f"/v1/coletas/{c1['id']}/resumo", headers=auth(token)).json()["para_revisar"]
        == 1
    )


def test_painel_do_admin_tem_numeros_da_plataforma(client, token, admin, detector):
    c = criar_coleta(client, token)
    _enviar(client, token, detector, c["id"], "Euglossa cognata", 0.9)
    client.post(
        "/v1/publico/contato",
        json={"nome": "Ana", "email": "ana@ex.com", "mensagem": "Quero saber dos planos."},
    )
    p = client.get("/v1/painel", headers=auth(admin)).json()["plataforma"]
    assert p["usuarios"] == 2 and p["fotos"] == 1 and p["fotos_hoje"] == 1
    assert p["mensagens_nao_respondidas"] == 1


# --- Fichas e catálogo ----------------------------------------------------------


FICHA = {
    "nome_popular": "Abelha-das-orquídeas",
    "autoria": "Moure, 1970",
    "descricao": "Abelha **verde-metálica** de *Euglossa* comum no Cerrado.\n\nSegundo parágrafo.",
    "caracteristicas": "- Língua longa\n- Machos coletam fragrâncias",
    "distribuicao": "Brasil central.",
    "fontes": "Moure, J. S. (1970). Exemplo.\nhttps://exemplo.org/artigo",
    "credito_imagem": "Foto: Maria Silva",
    "publicada": False,
}


def test_catalogo_publico_e_ficha(client, token, admin, detector):
    c = criar_coleta(client, token, uf="MT", data_coleta="2025-11-02")
    _enviar(client, token, detector, c["id"], "Euglossa cognata", 0.9, 1)
    _enviar(client, token, detector, c["id"], "Euglossa cognata", 0.9, 2)
    # Coleta fora do mapa geral não entra nos números públicos
    privada = criar_coleta(client, token, uf="GO", publica_no_mapa=False)
    _enviar(client, token, detector, privada["id"], "Euglossa cognata", 0.9, 3)
    # Espécie informada numa correção: sem ficha publicada, não aparece no catálogo
    f = _enviar(client, token, detector, c["id"], "Euglossa cognata", 0.9, 4)
    client.post(
        f"/v1/fotos/{f['id']}/revisao",
        json={"acao": "corrigir", "especie": "Eulaema nigrita"},
        headers=auth(token),
    )
    cognata = _id_especie(client, token, "Euglossa cognata")
    nigrita = _id_especie(client, token, "Eulaema nigrita")

    # Sem login
    lista = client.get("/v1/publico/especies").json()
    nomes = [e["nome_cientifico"] for e in lista]
    assert "Euglossa cognata" in nomes and "Euglossa modestior" in nomes  # modelo reconhece
    assert "Eulaema nigrita" not in nomes
    item = next(e for e in lista if e["id"] == cognata)
    assert item["ocorrencias"] == 2 and item["ficha_publicada"] is False and item["resumo"] is None

    d = client.get(f"/v1/publico/especies/{cognata}").json()
    assert d["ficha"] is None
    assert d["estatisticas"]["ocorrencias"] == 2 and d["estatisticas"]["coletas"] == 1
    assert d["estatisticas"]["estados"] == [{"uf": "MT", "nome": "Mato Grosso", "ocorrencias": 2}]
    assert d["estatisticas"]["primeiro_ano"] == 2025
    assert client.get(f"/v1/publico/especies/{nigrita}").status_code == 404

    # Rascunho: o público não vê
    r = client.put(f"/v1/admin/especies/{cognata}/ficha", json=FICHA, headers=auth(admin))
    assert r.status_code == 200, r.text
    assert r.json()["atualizado_por"] == "Admin"
    assert client.get(f"/v1/publico/especies/{cognata}").json()["ficha"] is None
    especies = client.get("/v1/especies", headers=auth(admin)).json()
    assert next(e for e in especies if e["id"] == cognata)["ficha"] == "rascunho"

    # Publicada
    client.put(
        f"/v1/admin/especies/{cognata}/ficha",
        json={**FICHA, "publicada": True},
        headers=auth(admin),
    )
    d = client.get(f"/v1/publico/especies/{cognata}").json()
    assert d["ficha"]["descricao"].startswith("Abelha **verde")
    assert d["ficha"]["atualizado_por"] is None  # o nome de quem editou não é público
    assert d["nome_popular"] == "Abelha-das-orquídeas"
    item = next(e for e in client.get("/v1/publico/especies").json() if e["id"] == cognata)
    assert item["resumo"] == "Abelha verde-metálica de Euglossa comum no Cerrado."

    # Ficha publicada de espécie fora do modelo passa a aparecer
    client.put(
        f"/v1/admin/especies/{nigrita}/ficha",
        json={**FICHA, "publicada": True},
        headers=auth(admin),
    )
    assert client.get(f"/v1/publico/especies/{nigrita}").status_code == 200


def test_ficha_validacoes_e_permissoes(client, token, admin, detector):
    c = criar_coleta(client, token)
    _enviar(client, token, detector, c["id"], "Euglossa cognata", 0.9)
    eid = _id_especie(client, token, "Euglossa cognata")
    url = f"/v1/admin/especies/{eid}/ficha"
    assert client.put(url, json=FICHA, headers=auth(token)).status_code == 403
    assert client.get(url, headers=auth(token)).status_code == 403
    r = client.put(url, json={"publicada": True, "descricao": "   "}, headers=auth(admin))
    assert r.status_code == 400
    assert (
        client.put("/v1/admin/especies/9999/ficha", json=FICHA, headers=auth(admin)).status_code
        == 404
    )
    # Ficha vazia ainda não criada
    assert client.get(url, headers=auth(admin)).json()["descricao"] is None


def test_imagem_da_ficha(client, token, admin, detector):
    import io

    from PIL import Image

    c = criar_coleta(client, token)
    _enviar(client, token, detector, c["id"], "Euglossa cognata", 0.9)
    eid = _id_especie(client, token, "Euglossa cognata")
    url = f"/v1/admin/especies/{eid}/ficha/imagem"
    files = {"arquivo": ("asa.jpg", imagem(tamanho=(2400, 1200), gps=(-15.6, -56.1)), "image/jpeg")}
    r = client.post(url, files=files, headers=auth(admin))
    assert r.status_code == 200, r.text
    img = Image.open(io.BytesIO(client.get(r.json()["url_imagem"]).content))
    assert img.size == (1600, 800)
    assert not img.getexif()  # sem GPS na imagem pública

    ruim = {"arquivo": ("x.jpg", b"nao e imagem", "image/jpeg")}
    assert client.post(url, files=ruim, headers=auth(admin)).status_code == 400
    assert client.delete(url, headers=auth(admin)).json()["url_imagem"] is None


# --- Contato --------------------------------------------------------------------


def test_contato(client, admin, monkeypatch):
    enviados = []
    monkeypatch.setattr(
        "app.routers.contato.enviar_email",
        lambda para, assunto, texto: enviados.append((para, assunto, texto)),
    )
    dados = {
        "nome": "Ana Souza",
        "email": "ana@exemplo.com",
        "instituicao": "SEMA-MT",
        "assunto": "institucional",
        "mensagem": "Gostaria de usar o DBeeAS no monitoramento.",
    }
    r = client.post("/v1/publico/contato", json=dados)
    assert r.status_code == 201
    assert enviados[0][0] == "contato@dbeeas.com.br"
    assert "SEMA-MT" in enviados[0][2] and "Uso institucional" in enviados[0][1]

    # Robô (campo escondido preenchido): resposta igual, nada guardado
    assert (
        client.post("/v1/publico/contato", json={**dados, "site": "http://spam"}).status_code == 201
    )
    assert len(enviados) == 1

    assert client.post("/v1/publico/contato", json={**dados, "mensagem": "oi"}).status_code == 422
    assert client.post("/v1/publico/contato", json={**dados, "email": "x"}).status_code == 422

    lista = client.get("/v1/admin/mensagens", headers=auth(admin)).json()
    assert lista["total"] == 1 and lista["nao_respondidas"] == 1
    m = lista["itens"][0]
    r = client.patch(
        f"/v1/admin/mensagens/{m['id']}", json={"respondida": True}, headers=auth(admin)
    )
    assert r.json()["respondida"] is True
    assert (
        client.get("/v1/admin/mensagens?somente_nao_respondidas=true", headers=auth(admin)).json()[
            "total"
        ]
        == 0
    )


def test_contato_so_admin_le(client, token):
    assert client.get("/v1/admin/mensagens", headers=auth(token)).status_code == 403
