"""Armazenamento de arquivos (fotos, miniaturas e exportações).

Hoje os arquivos ficam numa pasta do servidor (volume do Docker). A interface
foi pensada para trocar depois por um armazenamento de objetos compatível com S3
(Cloudflare R2, Backblaze B2...) sem mudar o resto do código: basta criar outra
classe com os mesmos métodos.
"""

import hashlib
import hmac
import os
import shutil
import time
from pathlib import Path
from typing import Protocol

from app.config import get_settings


class Armazenamento(Protocol):
    def salvar(self, chave: str, dados: bytes) -> None: ...
    def ler(self, chave: str) -> bytes: ...
    def mover_para(self, chave: str, origem: Path) -> None: ...
    def pasta_temporaria(self) -> Path: ...
    def caminho(self, chave: str) -> Path: ...
    def existe(self, chave: str) -> bool: ...
    def apagar(self, chave: str) -> None: ...


class ArmazenamentoLocal:
    def __init__(self, raiz: str):
        self.raiz = Path(raiz).resolve()

    def caminho(self, chave: str) -> Path:
        destino = (self.raiz / chave).resolve()
        # Impede chaves como "../../etc/passwd"
        if self.raiz not in destino.parents:
            raise ValueError("Chave de arquivo inválida")
        return destino

    def salvar(self, chave: str, dados: bytes) -> None:
        destino = self.caminho(chave)
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporario = destino.with_suffix(destino.suffix + ".tmp")
        temporario.write_bytes(dados)
        os.replace(temporario, destino)  # grava por inteiro ou não grava

    def ler(self, chave: str) -> bytes:
        return self.caminho(chave).read_bytes()

    def mover_para(self, chave: str, origem: Path) -> None:
        """Guarda um arquivo grande já gravado em disco (sem carregar na memória)."""
        destino = self.caminho(chave)
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(origem, destino)

    def pasta_temporaria(self) -> Path:
        """Pasta para arquivos temporários no mesmo disco (mover fica instantâneo)."""
        pasta = self.raiz / "tmp"
        pasta.mkdir(parents=True, exist_ok=True)
        return pasta

    def existe(self, chave: str) -> bool:
        return self.caminho(chave).is_file()

    def apagar(self, chave: str) -> None:
        self.caminho(chave).unlink(missing_ok=True)


def get_armazenamento() -> Armazenamento:
    return ArmazenamentoLocal(get_settings().armazenamento_dir)


# --- Links assinados -------------------------------------------------------
# As imagens são exibidas com <img src="...">, que não envia o token de login.
# Por isso geramos links com prazo de validade e uma assinatura que só o
# servidor sabe calcular. Quem não recebeu o link não consegue montá-lo.


def _assinatura(chave: str, expira: int) -> str:
    segredo = get_settings().jwt_secret.encode()
    return hmac.new(segredo, f"{chave}:{expira}".encode(), hashlib.sha256).hexdigest()[:32]


def url_assinada(chave: str | None) -> str | None:
    if not chave:
        return None
    validade = get_settings().url_assinada_minutos * 60
    # Arredonda o prazo para o navegador conseguir guardar a imagem em cache
    expira = (int(time.time()) // 600 + 1) * 600 + validade
    return f"/v1/arquivos/{chave}?expira={expira}&assinatura={_assinatura(chave, expira)}"


def assinatura_valida(chave: str, expira: int, assinatura: str) -> bool:
    if expira < time.time():
        return False
    return hmac.compare_digest(_assinatura(chave, expira), assinatura)
