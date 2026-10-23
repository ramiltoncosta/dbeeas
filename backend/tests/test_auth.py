"""Testes de cadastro, login, sessão e recuperação de senha."""

from datetime import timedelta

from sqlalchemy import update

from app.db import SessionLocal
from app.models import TipoToken, Token
from app.security import agora
from tests.conftest import DADOS_CADASTRO, auth, cadastrar


def test_health(client):
    r = client.get("/health")
    assert r.json() == {"status": "ok", "banco": "ok"}


def test_cadastro_inicia_sessao_e_normaliza_email(client):
    dados = cadastrar(client)
    assert dados["usuario"]["email"] == "maria@exemplo.com"
    assert dados["usuario"]["perfil"] == "pesquisador"
    assert dados["usuario"]["consentimento_uso_fotos"] is True
    # Navegador: refresh token só no cookie, nunca no corpo da resposta
    assert dados["refresh_token"] is None
    assert "dbeeas_refresh" in client.cookies

    r = client.get("/v1/auth/eu", headers=auth(dados["access_token"]))
    assert r.status_code == 200
    assert r.json()["nome"] == "Maria Silva"


def test_cadastro_exige_aceite_dos_termos(client):
    r = client.post("/v1/auth/cadastro", json={**DADOS_CADASTRO, "aceite_termos": False})
    assert r.status_code == 422


def test_cadastro_nao_permite_escolher_admin(client):
    r = client.post("/v1/auth/cadastro", json={**DADOS_CADASTRO, "perfil": "admin"})
    assert r.status_code == 422


def test_cadastro_rejeita_senha_curta(client):
    r = client.post("/v1/auth/cadastro", json={**DADOS_CADASTRO, "senha": "123"})
    assert r.status_code == 422


def test_email_duplicado(client):
    cadastrar(client)
    r = client.post("/v1/auth/cadastro", json={**DADOS_CADASTRO, "email": "MARIA@exemplo.com"})
    assert r.status_code == 409


def test_login(client):
    cadastrar(client)
    client.cookies.clear()
    r = client.post("/v1/auth/login", json={"email": "maria@exemplo.com", "senha": "abelha-123"})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_login_senha_errada_e_email_inexistente_tem_mesma_mensagem(client):
    cadastrar(client)
    r1 = client.post("/v1/auth/login", json={"email": "maria@exemplo.com", "senha": "errada-123"})
    r2 = client.post("/v1/auth/login", json={"email": "ninguem@exemplo.com", "senha": "x"})
    assert r1.status_code == r2.status_code == 401
    assert r1.json() == r2.json()


def test_sem_token_ou_token_invalido(client):
    assert client.get("/v1/auth/eu").status_code == 401
    assert client.get("/v1/auth/eu", headers=auth("lixo")).status_code == 401


def test_refresh_pelo_cookie_gira_o_token(client):
    cadastrar(client)
    antigo = client.cookies.get("dbeeas_refresh")
    r = client.post("/v1/auth/refresh")
    assert r.status_code == 200
    novo = client.cookies.get("dbeeas_refresh")
    assert novo and novo != antigo


def test_reuso_de_refresh_token_encerra_todas_as_sessoes(client):
    cadastrar(client)
    roubado = client.cookies.get("dbeeas_refresh")
    assert client.post("/v1/auth/refresh").status_code == 200
    atual = client.cookies.get("dbeeas_refresh")

    # Alguém tenta usar o token antigo (já trocado)
    client.cookies.clear()
    r = client.post("/v1/auth/refresh", json={"refresh_token": roubado})
    assert r.status_code == 401
    # A sessão legítima também foi encerrada, por segurança
    r = client.post("/v1/auth/refresh", json={"refresh_token": atual})
    assert r.status_code == 401


def test_aplicativo_recebe_refresh_no_corpo(client):
    cadastrar(client)
    client.cookies.clear()
    r = client.post(
        "/v1/auth/login",
        json={"email": "maria@exemplo.com", "senha": "abelha-123"},
        headers={"X-Cliente": "app"},
    )
    refresh = r.json()["refresh_token"]
    assert refresh
    assert "dbeeas_refresh" not in client.cookies
    r = client.post(
        "/v1/auth/refresh", json={"refresh_token": refresh}, headers={"X-Cliente": "app"}
    )
    assert r.status_code == 200
    assert r.json()["refresh_token"] != refresh


def test_refresh_expirado(client):
    cadastrar(client)
    with SessionLocal() as db:
        db.execute(update(Token).values(expira_em=agora() - timedelta(minutes=1)))
        db.commit()
    assert client.post("/v1/auth/refresh").status_code == 401


def test_logout(client):
    cadastrar(client)
    token = client.cookies.get("dbeeas_refresh")
    r = client.post("/v1/auth/logout")
    assert r.status_code == 204
    r = client.post("/v1/auth/refresh", json={"refresh_token": token})
    assert r.status_code == 401


def test_recuperacao_de_senha(client, emails):
    cadastrar(client)
    sessao_antiga = client.cookies.get("dbeeas_refresh")

    r = client.post("/v1/auth/esqueci-senha", json={"email": "MARIA@exemplo.com"})
    assert r.status_code == 202
    assert len(emails) == 1
    token = emails[0]["link"].split("token=")[1]
    assert emails[0]["link"].startswith("http://localhost:5173/redefinir-senha?token=")

    r = client.post("/v1/auth/redefinir-senha", json={"token": token, "nova_senha": "nova-senha-1"})
    assert r.status_code == 200

    # Link só funciona uma vez
    r = client.post("/v1/auth/redefinir-senha", json={"token": token, "nova_senha": "outra-123"})
    assert r.status_code == 400
    # Sessões antigas foram encerradas
    r = client.post("/v1/auth/refresh", json={"refresh_token": sessao_antiga})
    assert r.status_code == 401
    # Senha nova funciona, a antiga não
    login = {"email": "maria@exemplo.com"}
    assert client.post("/v1/auth/login", json={**login, "senha": "nova-senha-1"}).status_code == 200
    assert client.post("/v1/auth/login", json={**login, "senha": "abelha-123"}).status_code == 401


def test_esqueci_senha_nao_revela_se_email_existe(client, emails):
    r = client.post("/v1/auth/esqueci-senha", json={"email": "ninguem@exemplo.com"})
    assert r.status_code == 202
    assert emails == []


def test_link_de_redefinicao_expirado(client, emails):
    cadastrar(client)
    client.post("/v1/auth/esqueci-senha", json={"email": "maria@exemplo.com"})
    token = emails[0]["link"].split("token=")[1]
    with SessionLocal() as db:
        db.execute(
            update(Token)
            .where(Token.tipo == TipoToken.redefinir_senha)
            .values(expira_em=agora() - timedelta(seconds=1))
        )
        db.commit()
    r = client.post("/v1/auth/redefinir-senha", json={"token": token, "nova_senha": "nova-senha-1"})
    assert r.status_code == 400


def test_limite_de_tentativas_de_login(client):
    from app.ratelimit import limiter

    limiter.enabled = True
    codigos = [
        client.post("/v1/auth/login", json={"email": "x@exemplo.com", "senha": "x"}).status_code
        for _ in range(12)
    ]
    assert codigos[:10] == [401] * 10
    assert codigos[-1] == 429
