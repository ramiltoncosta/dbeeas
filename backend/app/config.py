"""Configurações do backend, lidas de variáveis de ambiente (arquivo .env)."""

from functools import lru_cache
from typing import Annotated

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # "desenvolvimento" ou "producao"
    ambiente: str = "desenvolvimento"

    # Banco de dados
    database_url: str = "postgresql+psycopg://dbeeas:dbeeas@db:5432/dbeeas"

    # Tokens de acesso (JWT). Em produção, JWT_SECRET precisa ser um valor longo e secreto.
    jwt_secret: str = "segredo-de-desenvolvimento-nao-usar-em-producao"
    access_token_minutos: int = 15
    refresh_token_dias: int = 30
    redefinir_senha_minutos: int = 60

    # Cookie da sessão (refresh token) no navegador
    cookie_seguro: bool = False  # True em produção (só envia por HTTPS)
    cookie_dominio: str | None = None  # ex.: ".dbeeas.com.br" em produção

    # Endereços
    frontend_url: str = "http://localhost:5173"
    cors_origens: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    # E-mail. Sem SMTP_HOST, os e-mails só aparecem no log.
    smtp_host: str | None = None
    smtp_porta: int = 587
    smtp_usuario: str | None = None
    smtp_senha: str | None = None
    smtp_tls: bool = True
    email_remetente: str = "DBeeAS <nao-responda@dbeeas.com.br>"
    # Para onde vão as mensagens do formulário de contato
    email_contato: str = "contato@dbeeas.com.br"

    # Perfis
    # Se True, o perfil "pesquisador" só tem acesso à localização exata de
    # espécies sensíveis depois que um administrador aprovar.
    pesquisador_requer_aprovacao: bool = False

    # Detector (API do YOLO) e fila de processamento
    detector_url: str = "http://detector:8000"
    detector_timeout_s: int = 180
    redis_url: str = "redis://redis:6379/0"
    # True = processa na hora, sem Redis (usado nos testes)
    fila_sincrona: bool = False
    max_tentativas: int = 3
    # Fotos identificadas abaixo desta confiança e sem revisão: sugeridas para conferir
    confianca_revisao: float = 0.7

    # Arquivos (fotos, miniaturas, exportações)
    armazenamento_dir: str = "/data/arquivos"
    upload_max_mb: int = 15
    max_fotos_por_envio: int = 20
    # Fuso usado para a data das fotos quando o aparelho não grava o fuso
    fuso_horario_padrao: str = "America/Sao_Paulo"
    # Por quantos dias o ZIP de uma exportação fica disponível para baixar
    exportacao_dias: int = 7
    # Por quanto tempo os links das imagens valem
    url_assinada_minutos: int = 120

    # Limite de tentativas (login, cadastro, recuperação de senha)
    limite_auth: str = "10/minute"
    ratelimit_storage: str = "memory://"

    @model_validator(mode="after")
    def _checar_producao(self):
        if self.ambiente == "producao":
            if (
                self.jwt_secret.startswith("segredo-de-desenvolvimento")
                or len(self.jwt_secret) < 32
            ):
                raise ValueError(
                    "Em produção, defina JWT_SECRET com pelo menos 32 caracteres aleatórios "
                    "(gere com: openssl rand -hex 32)."
                )
            if not self.cookie_seguro:
                raise ValueError("Em produção, COOKIE_SEGURO precisa ser true.")
        return self

    @field_validator("cors_origens", mode="before")
    @classmethod
    def _separar_origens(cls, valor):
        # Permite escrever CORS_ORIGENS=https://a.com,https://b.com no .env
        if isinstance(valor, str) and not valor.startswith("["):
            return [o.strip() for o in valor.split(",") if o.strip()]
        return valor


@lru_cache
def get_settings() -> Settings:
    return Settings()
