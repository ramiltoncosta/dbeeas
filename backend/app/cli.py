"""Comandos de administração.

Criar o primeiro administrador:
    docker compose exec backend python -m app.cli criar-admin
"""

import argparse
import getpass
import sys

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Perfil, Usuario
from app.schemas import SENHA_MIN
from app.security import agora, gerar_hash_senha


def criar_admin() -> int:
    nome = input("Nome: ").strip()
    email = input("E-mail: ").strip().lower()
    senha = getpass.getpass(f"Senha (mínimo {SENHA_MIN} caracteres): ")
    if senha != getpass.getpass("Repita a senha: "):
        print("As senhas não conferem.")
        return 1
    if len(senha) < SENHA_MIN or not nome or "@" not in email:
        print("Dados inválidos.")
        return 1

    with SessionLocal() as db:
        existente = db.scalar(select(Usuario).where(Usuario.email == email))
        if existente:
            existente.perfil = Perfil.admin
            existente.ativo = True
            db.commit()
            print(f"A conta {email} já existia e agora é administradora.")
            return 0
        db.add(
            Usuario(
                nome=nome,
                email=email,
                senha_hash=gerar_hash_senha(senha),
                perfil=Perfil.admin,
                termos_aceitos_em=agora(),
            )
        )
        db.commit()
    print(f"Administrador {email} criado.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("criar-admin", help="Cria (ou promove) um administrador")
    args = parser.parse_args()
    if args.comando == "criar-admin":
        return criar_admin()
    return 1


if __name__ == "__main__":
    sys.exit(main())
