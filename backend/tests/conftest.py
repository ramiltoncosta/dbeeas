"""Configuração dos testes.

Os testes usam um banco PostgreSQL separado (dbeeas_test), recriado a cada
execução, e aplicam as migrações do Alembic, testando também as migrações.

Rodar dentro do Docker:
    docker compose exec backend pytest
"""

import os

import psycopg
import pytest
from sqlalchemy.engine import make_url

URL_BASE = os.environ.get(
    "TEST_DATABASE_URL",
    os.environ.get("DATABASE_URL", "postgresql+psycopg://dbeeas:dbeeas@db:5432/dbeeas"),
)
URL_TESTE = make_url(URL_BASE).set(database="dbeeas_test")
os.environ["DATABASE_URL"] = URL_TESTE.render_as_string(hide_password=False)
os.environ["SMTP_HOST"] = ""


def _recriar_banco():
    admin = make_url(URL_BASE).set(drivername="postgresql", database="postgres")
    with psycopg.connect(admin.render_as_string(hide_password=False), autocommit=True) as c:
        c.execute("DROP DATABASE IF EXISTS dbeeas_test WITH (FORCE)")
        c.execute("CREATE DATABASE dbeeas_test")


@pytest.fixture(scope="session", autouse=True)
def banco():
    from alembic.config import Config

    from alembic import command

    _recriar_banco()
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "alembic"))
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def limpar_tabelas(banco):
    yield
    from sqlalchemy import text

    from app.db import engine

    with engine.begin() as c:
        c.execute(text("TRUNCATE tokens, usuarios CASCADE"))


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app
    from app.ratelimit import limiter

    limiter.enabled = False
    limiter.reset()
    with TestClient(app) as c:
        yield c
    limiter.enabled = True


@pytest.fixture
def emails(monkeypatch):
    """Captura os e-mails enviados durante o teste."""
    enviados = []

    def falso(para, nome, link, minutos):
        enviados.append({"para": para, "nome": nome, "link": link})

    monkeypatch.setattr("app.routers.auth.email_redefinir_senha", falso)
    return enviados


DADOS_CADASTRO = {
    "nome": "Maria Silva",
    "email": "Maria@Exemplo.com",
    "senha": "abelha-123",
    "perfil": "pesquisador",
    "instituicao": "UFMT",
    "aceite_termos": True,
    "consentimento_uso_fotos": True,
}


def cadastrar(client, **extra):
    dados = {**DADOS_CADASTRO, **extra}
    r = client.post("/v1/auth/cadastro", json=dados)
    assert r.status_code == 201, r.text
    return r.json()


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin(client):
    """Cria um administrador e devolve o token de acesso."""
    from sqlalchemy import update

    from app.db import SessionLocal
    from app.models import Perfil, Usuario

    cadastrar(client, email="admin@dbeeas.com.br", nome="Admin")
    with SessionLocal() as db:
        db.execute(
            update(Usuario)
            .where(Usuario.email == "admin@dbeeas.com.br")
            .values(perfil=Perfil.admin)
        )
        db.commit()
    r = client.post("/v1/auth/login", json={"email": "admin@dbeeas.com.br", "senha": "abelha-123"})
    client.cookies.clear()
    return r.json()["access_token"]
