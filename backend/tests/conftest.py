"""Configuração dos testes.

Os testes usam um banco PostgreSQL separado (dbeeas_test), recriado a cada
execução, e aplicam as migrações do Alembic, testando também as migrações.

Rodar dentro do Docker:
    docker compose exec backend pytest
"""

import io
import os
import tempfile

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
# Fotos processadas na hora (sem Redis) e arquivos numa pasta temporária
os.environ["FILA_SINCRONA"] = "true"
os.environ["ARMAZENAMENTO_DIR"] = tempfile.mkdtemp(prefix="dbeeas-testes-")


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
        c.execute(
            text(
                "TRUNCATE mensagens_contato, fichas_especies, exportacoes, revisoes, "
                "identificacoes, fotos, coletas, modelos, especies, tokens, usuarios "
                "RESTART IDENTITY CASCADE"
            )
        )


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


# --- Coletas e fotos ---------------------------------------------------------


class DetectorFalso:
    """Substitui o detector (YOLO) nos testes. Responde o que for configurado."""

    def __init__(self):
        self.especie = "Euglossa cognata"
        self.confianca = 0.93
        self.versao = "teste-v1"
        self.erro: Exception | None = None
        self.falhas_temporarias = 0  # quantas vezes falha antes de funcionar
        self.chamadas = 0

    def detectar(self, dados, tipo_mime, nome, anotar=False):
        from app.detector import DetectorIndisponivel

        self.chamadas += 1
        if self.falhas_temporarias > 0:
            self.falhas_temporarias -= 1
            raise DetectorIndisponivel("fora do ar")
        if self.erro:
            raise self.erro
        identificada = self.confianca >= 0.5
        r = {
            "identificada": identificada,
            "especie": self.especie if identificada else None,
            "confianca": self.confianca,
            "mensagem": None,
            "deteccoes": [
                {
                    "especie": self.especie,
                    "classe_id": 4,
                    "confianca": self.confianca,
                    "caixa": {"x1": 1.0, "y1": 2.0, "x2": 30.0, "y2": 20.0},
                }
            ],
            "imagem": {"largura": 64, "altura": 48},
            "versao_modelo": self.versao,
        }
        if anotar:
            r["imagem_anotada"] = "base64..."
        return r

    def saude(self):
        return {
            "status": "ok",
            "especies": ["Euglossa cognata", "Euglossa modestior"],
            "versao_modelo": self.versao,
        }


@pytest.fixture
def detector(monkeypatch):
    falso = DetectorFalso()
    monkeypatch.setattr("app.detector.detectar", falso.detectar)
    monkeypatch.setattr("app.detector.saude", falso.saude)
    return falso


def imagem(
    cor=(200, 150, 50),
    formato="JPEG",
    tamanho=(64, 48),
    gps: tuple[float, float] | None = None,
    data: str | None = None,
    orientacao: int | None = None,
) -> bytes:
    """Gera uma imagem de teste, opcionalmente com GPS e data no EXIF."""
    from PIL import ExifTags, Image

    img = Image.new("RGB", tamanho, cor)
    exif = Image.Exif()
    if gps:
        lat, lon = gps

        def dms(v):
            v = abs(v)
            g = int(v)
            m = int((v - g) * 60)
            s = round(((v - g) * 60 - m) * 60, 4)
            return (float(g), float(m), float(s))

        exif[ExifTags.IFD.GPSInfo] = {
            ExifTags.GPS.GPSLatitudeRef: "S" if lat < 0 else "N",
            ExifTags.GPS.GPSLatitude: dms(lat),
            ExifTags.GPS.GPSLongitudeRef: "W" if lon < 0 else "E",
            ExifTags.GPS.GPSLongitude: dms(lon),
        }
    if data:
        exif.get_ifd(ExifTags.IFD.Exif)[ExifTags.Base.DateTimeOriginal] = data
    if orientacao:
        exif[ExifTags.Base.Orientation] = orientacao
    saida = io.BytesIO()
    img.save(saida, format=formato, exif=exif.tobytes() if len(exif) else b"")
    return saida.getvalue()


def criar_coleta(client, token, **extra):
    dados = {"nome": "Coleta teste", **extra}
    r = client.post("/v1/coletas", json=dados, headers=auth(token))
    assert r.status_code == 201, r.text
    return r.json()


def enviar(client, token, coleta_id, *arquivos):
    files = [("arquivos", (nome, dados, "image/jpeg")) for nome, dados in arquivos]
    return client.post(f"/v1/coletas/{coleta_id}/fotos", files=files, headers=auth(token))
