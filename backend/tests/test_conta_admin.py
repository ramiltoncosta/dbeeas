"""Testes de Minha conta (LGPD), administração e regras de perfil."""

import uuid

from app.config import get_settings
from app.deps import pode_ver_localizacao_exata
from app.models import Perfil, Usuario
from tests.conftest import auth, cadastrar


def test_atualizar_conta_e_consentimento(client):
    t = cadastrar(client, consentimento_uso_fotos=False)["access_token"]
    r = client.patch(
        "/v1/eu",
        json={"nome": "Maria S.", "instituicao": "", "consentimento_uso_fotos": True},
        headers=auth(t),
    )
    assert r.status_code == 200
    assert r.json()["nome"] == "Maria S."
    assert r.json()["instituicao"] is None
    assert r.json()["consentimento_uso_fotos"] is True


def test_trocar_senha(client):
    t = cadastrar(client)["access_token"]
    r = client.post(
        "/v1/eu/senha",
        json={"senha_atual": "errada", "nova_senha": "nova-senha-1"},
        headers=auth(t),
    )
    assert r.status_code == 400
    r = client.post(
        "/v1/eu/senha",
        json={"senha_atual": "abelha-123", "nova_senha": "nova-senha-1"},
        headers=auth(t),
    )
    assert r.status_code == 200
    login = {"email": "maria@exemplo.com", "senha": "nova-senha-1"}
    assert client.post("/v1/auth/login", json=login).status_code == 200


def test_exportar_meus_dados(client):
    t = cadastrar(client)["access_token"]
    r = client.get("/v1/eu/dados", headers=auth(t))
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    assert r.json()["conta"]["email"] == "maria@exemplo.com"
    assert r.json()["consentimentos"]["uso_das_fotos_para_melhorar_o_modelo"] is True


def test_excluir_conta(client):
    t = cadastrar(client)["access_token"]
    r = client.request("DELETE", "/v1/eu", json={"senha": "errada"}, headers=auth(t))
    assert r.status_code == 400
    r = client.request("DELETE", "/v1/eu", json={"senha": "abelha-123"}, headers=auth(t))
    assert r.status_code == 204
    assert client.get("/v1/auth/eu", headers=auth(t)).status_code == 401
    login = {"email": "maria@exemplo.com", "senha": "abelha-123"}
    assert client.post("/v1/auth/login", json=login).status_code == 401


def test_unico_admin_nao_pode_se_excluir(client, admin):
    r = client.request("DELETE", "/v1/eu", json={"senha": "abelha-123"}, headers=auth(admin))
    assert r.status_code == 400


def test_usuario_comum_nao_acessa_admin(client):
    t = cadastrar(client)["access_token"]
    assert client.get("/v1/admin/usuarios", headers=auth(t)).status_code == 403


def test_admin_lista_busca_e_atualiza_usuarios(client, admin):
    cadastrar(client, email="joao@exemplo.com", nome="João", perfil="estudante")
    client.cookies.clear()

    r = client.get("/v1/admin/usuarios", params={"busca": "joão"}, headers=auth(admin))
    assert r.status_code == 200
    assert r.json()["total"] == 1
    joao = r.json()["itens"][0]

    r = client.patch(
        f"/v1/admin/usuarios/{joao['id']}", json={"perfil": "pesquisador"}, headers=auth(admin)
    )
    assert r.json()["perfil"] == "pesquisador"

    # Desativar desconecta e impede login
    r = client.patch(f"/v1/admin/usuarios/{joao['id']}", json={"ativo": False}, headers=auth(admin))
    assert r.json()["ativo"] is False
    login = {"email": "joao@exemplo.com", "senha": "abelha-123"}
    assert client.post("/v1/auth/login", json=login).status_code == 403


def test_admin_nao_pode_se_desativar(client, admin):
    eu = client.get("/v1/auth/eu", headers=auth(admin)).json()
    r = client.patch(f"/v1/admin/usuarios/{eu['id']}", json={"ativo": False}, headers=auth(admin))
    assert r.status_code == 400


def test_aprovacao_de_pesquisador(client, admin, monkeypatch):
    monkeypatch.setattr(get_settings(), "pesquisador_requer_aprovacao", True)
    cadastrar(client, email="pesq@exemplo.com")
    client.cookies.clear()
    r = client.get("/v1/admin/usuarios", params={"aguardando_aprovacao": True}, headers=auth(admin))
    assert r.json()["total"] == 1
    assert r.json()["itens"][0]["perfil_aprovado"] is False


def _usuario(perfil, aprovado=True):
    return Usuario(id=uuid.uuid4(), perfil=perfil, perfil_aprovado=aprovado)


def test_regra_localizacao_exata(monkeypatch):
    dono = uuid.uuid4()
    estudante = _usuario(Perfil.estudante)
    orgao = _usuario(Perfil.orgao_publico)
    pesquisador = _usuario(Perfil.pesquisador, aprovado=False)

    assert pode_ver_localizacao_exata(_usuario(Perfil.admin), dono)
    assert pode_ver_localizacao_exata(estudante, estudante.id)  # dono da foto
    assert not pode_ver_localizacao_exata(estudante, dono)
    assert not pode_ver_localizacao_exata(orgao, dono)
    assert pode_ver_localizacao_exata(pesquisador, dono)  # aprovação desligada

    monkeypatch.setattr(get_settings(), "pesquisador_requer_aprovacao", True)
    assert not pode_ver_localizacao_exata(pesquisador, dono)
    assert pode_ver_localizacao_exata(_usuario(Perfil.pesquisador, aprovado=True), dono)
