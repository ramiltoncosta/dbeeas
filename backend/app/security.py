"""Senhas, tokens JWT e tokens de uso único."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.config import get_settings

_hasher = PasswordHash.recommended()  # argon2
# Usado para gastar o mesmo tempo quando o e-mail não existe
# (evita que alguém descubra quais e-mails têm conta pelo tempo de resposta)
_HASH_FALSO = _hasher.hash("senha-inexistente")

ALGORITMO = "HS256"


def agora() -> datetime:
    return datetime.now(UTC)


def gerar_hash_senha(senha: str) -> str:
    return _hasher.hash(senha)


def verificar_senha(senha: str, senha_hash: str | None) -> bool:
    if senha_hash is None:
        _hasher.verify(senha, _HASH_FALSO)
        return False
    return _hasher.verify(senha, senha_hash)


def criar_access_token(usuario_id: uuid.UUID, perfil: str) -> tuple[str, int]:
    """Token de acesso de curta duração. Retorna (token, segundos até expirar)."""
    s = get_settings()
    expira_em = s.access_token_minutos * 60
    payload = {
        "sub": str(usuario_id),
        "perfil": perfil,
        "tipo": "access",
        "iat": agora(),
        "exp": agora() + timedelta(seconds=expira_em),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=ALGORITMO), expira_em


def ler_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITMO])
    except jwt.PyJWTError:
        return None
    if payload.get("tipo") != "access":
        return None
    return payload


def gerar_token_opaco() -> tuple[str, str]:
    """Gera um token aleatório. Retorna (token para o usuário, hash para o banco)."""
    token = secrets.token_urlsafe(48)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
