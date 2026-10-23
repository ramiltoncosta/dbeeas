"""Testes da etapa 7: planos, assinaturas, limites de uso e pagamento."""

import json
from datetime import timedelta

import pytest
from sqlalchemy import update

from app.db import SessionLocal
from app.models import Assinatura
from app.security import agora
from tests.conftest import auth, cadastrar, criar_coleta, enviar, imagem


@pytest.fixture
def token(client):
    return cadastrar(client)["access_token"]


def _plano(client, token):
    r = client.get("/v1/eu/plano", headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def _criar_plano(client, admin, **extra):
    dados = {"codigo": "mini", "nome": "Mini", "limite_fotos_mes": 3, **extra}
    r = client.post("/v1/admin/planos", json=dados, headers=auth(admin))
    assert r.status_code == 201, r.text
    return r.json()


def _definir(client, admin, usuario_id, plano_id, **extra):
    r = client.post(
        f"/v1/admin/usuarios/{usuario_id}/assinaturas",
        json={"plano_id": plano_id, **extra},
        headers=auth(admin),
    )
    assert r.status_code == 201, r.text
    return r.json()


def _eu(client, token):
    return client.get("/v1/auth/eu", headers=auth(token)).json()


def _foto(i):
    return (f"f{i}.jpg", imagem(cor=(i * 37 % 255, i * 11 % 255, 90)))


def test_cadastro_ganha_teste_no_plano_do_perfil(client):
    for perfil, plano in [
        ("pesquisador", "pesquisador"),
        ("estudante", "estudante"),
        ("orgao_publico", "institucional"),
    ]:
        t = cadastrar(client, email=f"{perfil}@ex.com", perfil=perfil)["access_token"]
        p = _plano(client, t)
        assert p["status"] == "teste" and p["plano"]["codigo"] == plano
        assert p["pode_enviar"] is True and p["uso"]["usadas"] == 0
        dias = p["assinatura"]["fim"][:10]
        assert dias == (agora() + timedelta(days=30)).date().isoformat()


def test_planos_publicos(client, admin):
    _criar_plano(client, admin, codigo="oculto", nome="Oculto", publico=False)
    codigos = [p["codigo"] for p in client.get("/v1/planos").json()]
    assert codigos == ["estudante", "pesquisador", "institucional"]


def test_limite_do_mes(client, token, admin, detector):
    mini = _criar_plano(client, admin)
    _definir(client, admin, _eu(client, token)["id"], mini["id"], status="ativa")
    c = criar_coleta(client, token)

    assert len(enviar(client, token, c["id"], _foto(1)).json()["aceitas"]) == 1
    # Foto repetida e arquivo inválido não gastam saldo
    r = enviar(client, token, c["id"], _foto(1), ("x.jpg", b"nada"))
    assert r.json()["aceitas"] == []
    # Lote maior que o saldo: entra até o limite, o resto é recusado com o motivo
    r = enviar(client, token, c["id"], _foto(2), _foto(3), _foto(4)).json()
    assert len(r["aceitas"]) == 2
    assert r["rejeitadas"] == [
        {"arquivo": "f4.jpg", "motivo": "Limite de fotos do plano atingido neste mês."}
    ]

    p = _plano(client, token)
    assert p["uso"] == {**p["uso"], "fotos": 3, "usadas": 3, "limite": 3, "restantes": 0}
    assert p["pode_enviar"] is False and "3 fotos" in p["motivo_bloqueio"]

    r = enviar(client, token, c["id"], _foto(5))
    assert r.status_code == 403 and "renova no dia 1º" in r.json()["detail"]

    # Apagar fotos não devolve o saldo
    foto = client.get(f"/v1/coletas/{c['id']}/fotos", headers=auth(token)).json()["itens"][0]
    client.delete(f"/v1/fotos/{foto['id']}", headers=auth(token))
    assert _plano(client, token)["uso"]["restantes"] == 0

    # Reprocessar não conta
    assert _plano(client, token)["uso"]["fotos"] == 3


def test_identificacao_rapida_conta_e_devolve_se_falhar(client, token, admin, detector):
    from app.detector import DetectorIndisponivel

    mini = _criar_plano(client, admin, limite_fotos_mes=2)
    _definir(client, admin, _eu(client, token)["id"], mini["id"])

    def identificar():
        return client.post(
            "/v1/identificar",
            files={"arquivo": ("a.jpg", imagem(), "image/jpeg")},
            headers=auth(token),
        )

    assert identificar().status_code == 200
    detector.erro = DetectorIndisponivel("fora")
    assert identificar().status_code == 503
    assert _plano(client, token)["uso"]["identificacoes_rapidas"] == 1  # a que falhou voltou
    detector.erro = None
    assert identificar().status_code == 200
    r = identificar()
    assert r.status_code == 403
    # As fotos das coletas usam o mesmo saldo
    c = criar_coleta(client, token)
    assert enviar(client, token, c["id"], _foto(1)).status_code == 403


@pytest.mark.parametrize(
    ("status", "trecho"),
    [("suspensa", "suspensa"), ("cancelada", "cancelada")],
)
def test_assinatura_que_nao_libera(client, token, admin, status, trecho):
    _definir(client, admin, _eu(client, token)["id"], 2, status=status)
    c = criar_coleta(client, token)
    r = enviar(client, token, c["id"], _foto(1))
    assert r.status_code == 403 and trecho in r.json()["detail"]


def test_teste_vencido_bloqueia(client, token):
    with SessionLocal() as db:
        db.execute(update(Assinatura).values(fim=agora() - timedelta(minutes=1)))
        db.commit()
    p = _plano(client, token)
    assert p["status"] == "expirada" and p["pode_enviar"] is False
    c = criar_coleta(client, token)
    r = enviar(client, token, c["id"], _foto(1))
    assert r.status_code == 403 and "venceu" in r.json()["detail"]


def test_administrador_nao_tem_limite(client, admin, detector):
    p = _plano(client, admin)
    assert p["status"] == "ilimitado" and p["pode_enviar"] and p["uso"]["limite"] is None
    c = criar_coleta(client, admin)
    assert len(enviar(client, admin, c["id"], _foto(1), _foto(2)).json()["aceitas"]) == 2


def test_pedido_de_plano_e_ativacao_manual(client, token, admin, monkeypatch):
    avisos = []
    monkeypatch.setattr("app.pagamentos.enviar_email", lambda *a: avisos.append(a))
    eu = _eu(client, token)

    r = client.post("/v1/eu/plano/pedido", json={"plano_id": 3}, headers=auth(token))
    assert r.status_code == 201, r.text
    assert "equipe do DBeeAS" in r.json()["mensagem"] and avisos
    assert (
        client.post("/v1/eu/plano/pedido", json={"plano_id": 3}, headers=auth(token)).status_code
        == 409
    )

    # O teste continua valendo enquanto o pedido não é ativado
    p = _plano(client, token)
    assert p["status"] == "teste" and p["pedido"]["plano"]["codigo"] == "institucional"
    lista = client.get("/v1/admin/usuarios?pedidos_de_plano=true", headers=auth(admin)).json()
    assert [u["id"] for u in lista["itens"]] == [eu["id"]]
    assert lista["itens"][0]["plano"]["pedido"] == "Institucional"

    p = _definir(client, admin, eu["id"], 3, status="ativa", dias=30, observacao="Pago por PIX")
    assert (
        p["status"] == "ativa" and p["plano"]["codigo"] == "institucional" and p["pedido"] is None
    )
    assert (
        client.get("/v1/admin/usuarios?pedidos_de_plano=true", headers=auth(admin)).json()["total"]
        == 0
    )

    historico = client.get(f"/v1/admin/usuarios/{eu['id']}/assinaturas", headers=auth(admin)).json()
    assert [h["status"] for h in historico] == ["ativa", "pendente", "teste"]
    assert historico[0]["alterado_por"] == "Admin" and historico[0]["observacao"] == "Pago por PIX"


def test_desistir_do_pedido(client, token):
    client.post("/v1/eu/plano/pedido", json={"plano_id": 1}, headers=auth(token))
    assert client.delete("/v1/eu/plano/pedido", headers=auth(token)).status_code == 200
    p = _plano(client, token)
    assert p["pedido"] is None and p["status"] == "teste"
    assert client.delete("/v1/eu/plano/pedido", headers=auth(token)).status_code == 404


def test_plano_sem_exportacao(client, token, admin, detector):
    sem = _criar_plano(client, admin, codigo="basico", nome="Básico", permite_exportacao=False)
    _definir(client, admin, _eu(client, token)["id"], sem["id"])
    c = criar_coleta(client, token)
    enviar(client, token, c["id"], _foto(1))
    r = client.post(f"/v1/coletas/{c['id']}/exportacoes", json={}, headers=auth(token))
    assert r.status_code == 403


def test_admin_edita_planos(client, token, admin):
    p = _criar_plano(client, admin, preco_mensal_centavos=2990)
    assert (
        client.post(
            "/v1/admin/planos", json={"codigo": "mini", "nome": "Xis"}, headers=auth(admin)
        ).status_code
        == 409
    )
    r = client.patch(
        f"/v1/admin/planos/{p['id']}",
        json={"preco_mensal_centavos": None, "limite_fotos_mes": 50, "nome": None},
        headers=auth(admin),
    )
    assert r.json()["preco_mensal_centavos"] is None and r.json()["limite_fotos_mes"] == 50
    assert r.json()["nome"] == "Mini"
    assert (
        client.post(
            "/v1/admin/planos", json={"codigo": "x y", "nome": "Xis"}, headers=auth(admin)
        ).status_code
        == 422
    )
    assert client.get("/v1/admin/planos", headers=auth(token)).status_code == 403


# --- Serviço de pagamento (um falso, para provar que a interface funciona) ------


class GatewayFalso:
    nome = "falso"

    def iniciar_assinatura(self, usuario, plano, pedido_id):
        from app.pagamentos import Cobranca

        return Cobranca(
            mensagem="Pague no link",
            codigo_externo=f"sub_{pedido_id[:8]}",
            url_pagamento="https://pagar.exemplo/123",
        )

    def cancelar_assinatura(self, codigo_externo):
        pass

    def ler_webhook(self, cabecalhos, corpo):
        from app.pagamentos import AssinaturaInvalida, EventoPagamento

        if cabecalhos.get("x-token") != "segredo":
            raise AssinaturaInvalida()
        d = json.loads(corpo)
        return EventoPagamento(codigo_externo=d["id"], tipo=d["tipo"])


def test_pagamento_automatico_pela_interface(client, token, monkeypatch):
    from app.config import get_settings
    from app.pagamentos import GATEWAYS

    monkeypatch.setitem(GATEWAYS, "falso", GatewayFalso)
    monkeypatch.setattr(get_settings(), "gateway_pagamento", "falso")

    r = client.post("/v1/eu/plano/pedido", json={"plano_id": 2}, headers=auth(token)).json()
    assert r["url_pagamento"] == "https://pagar.exemplo/123"
    codigo = f"sub_{r['pedido']['id'][:8]}"

    def aviso(tipo, token_="segredo", gateway="falso"):
        return client.post(
            f"/v1/pagamentos/webhook/{gateway}",
            content=json.dumps({"id": codigo, "tipo": tipo}),
            headers={"x-token": token_},
        )

    assert aviso("pago", token_="errado").status_code == 401
    assert aviso("pago", gateway="outro").status_code == 404
    assert aviso("pago").status_code == 200
    p = _plano(client, token)
    assert p["status"] == "ativa" and p["plano"]["codigo"] == "pesquisador"
    assert p["assinatura"]["fim"][:10] == (agora() + timedelta(days=31)).date().isoformat()

    assert aviso("atrasado").status_code == 200
    p = _plano(client, token)
    assert p["status"] == "suspensa" and p["pode_enviar"] is False

    aviso("pago")
    assert _plano(client, token)["status"] == "ativa"


def test_foto_da_identificacao_rapida_nao_conta_duas_vezes(client, token, detector):
    foto = imagem(cor=(10, 200, 30))
    r = client.post(
        "/v1/identificar", files={"arquivo": ("a.jpg", foto, "image/jpeg")}, headers=auth(token)
    )
    assert r.status_code == 200
    c = criar_coleta(client, token)
    enviar(client, token, c["id"], ("a.jpg", foto))  # salva a mesma foto numa coleta
    uso = _plano(client, token)["uso"]
    assert uso["usadas"] == 1 and uso["identificacoes_rapidas"] == 1 and uso["fotos"] == 0
    # Numa segunda coleta, a mesma foto já conta (o crédito vale uma vez)
    c2 = criar_coleta(client, token)
    enviar(client, token, c2["id"], ("a.jpg", foto))
    assert _plano(client, token)["uso"]["usadas"] == 2
