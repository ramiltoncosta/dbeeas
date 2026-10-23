"""Limite de tentativas por endereço IP (protege login e cadastro contra robôs)."""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=get_settings().ratelimit_storage,
    headers_enabled=False,
)
