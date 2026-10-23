"""Formatos de entrada e saída da API (validados pelo Pydantic)."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import Perfil

SENHA_MIN = 8

# Perfis que a própria pessoa pode escolher no cadastro (admin não)
PerfilCadastro = Literal["pesquisador", "orgao_publico", "estudante"]


def _normalizar_email(valor: str) -> str:
    return valor.strip().lower()


# E-mail sempre guardado em minúsculas, para "Fulano@X.com" e "fulano@x.com" serem a mesma conta
Email = Annotated[EmailStr, AfterValidator(_normalizar_email)]


class CadastroIn(BaseModel):
    nome: str = Field(min_length=2, max_length=150)
    email: Email
    senha: str = Field(min_length=SENHA_MIN, max_length=128)
    perfil: PerfilCadastro
    instituicao: str | None = Field(default=None, max_length=200)
    aceite_termos: bool
    consentimento_uso_fotos: bool = False

    @field_validator("nome", "instituicao")
    @classmethod
    def _limpar(cls, v):
        return v.strip() if isinstance(v, str) else v


class LoginIn(BaseModel):
    email: Email
    senha: str = Field(max_length=128)


class RefreshIn(BaseModel):
    refresh_token: str | None = None


class EsqueciSenhaIn(BaseModel):
    email: Email


class RedefinirSenhaIn(BaseModel):
    token: str
    nova_senha: str = Field(min_length=SENHA_MIN, max_length=128)


class TrocarSenhaIn(BaseModel):
    senha_atual: str = Field(max_length=128)
    nova_senha: str = Field(min_length=SENHA_MIN, max_length=128)


class AtualizarContaIn(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=150)
    instituicao: str | None = Field(default=None, max_length=200)
    consentimento_uso_fotos: bool | None = None


class ExcluirContaIn(BaseModel):
    senha: str = Field(max_length=128)


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome: str
    email: str
    perfil: Perfil
    instituicao: str | None
    ativo: bool
    perfil_aprovado: bool
    consentimento_uso_fotos: bool
    criado_em: datetime


class UsuarioAdminOut(UsuarioOut):
    ultimo_login_em: datetime | None
    termos_aceitos_em: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    # Só preenchido para o aplicativo (cabeçalho X-Cliente: app).
    # No navegador, o refresh token fica num cookie protegido.
    refresh_token: str | None = None
    usuario: UsuarioOut


class AdminAtualizarUsuarioIn(BaseModel):
    perfil: Perfil | None = None
    ativo: bool | None = None
    perfil_aprovado: bool | None = None


class PaginaUsuarios(BaseModel):
    itens: list[UsuarioAdminOut]
    total: int
    pagina: int
    por_pagina: int


class Mensagem(BaseModel):
    mensagem: str
