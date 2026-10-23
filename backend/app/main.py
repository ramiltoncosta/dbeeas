"""DBeeAS – backend principal."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.config import get_settings
from app.db import SessionLocal
from app.ratelimit import limiter
from app.routers import (
    admin,
    arquivos,
    auth,
    coletas,
    especies,
    eu,
    exportacoes,
    fotos,
    identificar,
    mapa,
)

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="DBeeAS",
    description="Sistema inteligente de reconhecimento de abelhas pela asa. "
    "API usada pelo site e pelo aplicativo.",
    version="0.6.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origens,
    allow_credentials=True,  # necessário para o cookie da sessão
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (
    auth.router,
    eu.router,
    coletas.router,
    fotos.router,
    especies.router,
    mapa.router,
    exportacoes.router,
    identificar.router,
    arquivos.router,
    admin.router,
):
    app.include_router(r, prefix="/v1")


@app.get("/health", tags=["Sistema"])
def health():
    """Verifica se a API e o banco de dados estão funcionando."""
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        banco = "ok"
    except Exception:
        banco = "erro"
    return {"status": "ok" if banco == "ok" else "degradado", "banco": banco}
