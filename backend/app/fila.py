"""Fila de processamento (Redis + RQ).

O backend só coloca o pedido na fila e responde na hora. O worker (outro
contêiner) pega um pedido por vez e faz o trabalho pesado.

Para ver a fila funcionando:
    docker compose logs -f worker
"""

import logging
from functools import lru_cache

from redis import Redis
from rq import Queue, Retry

from app.config import get_settings

log = logging.getLogger("dbeeas.fila")

FILA_FOTOS = "fotos"


@lru_cache
def _redis() -> Redis:
    return Redis.from_url(get_settings().redis_url)


def fila(nome: str = FILA_FOTOS) -> Queue:
    return Queue(nome, connection=_redis())


def enfileirar_fotos(ids: list[str]) -> None:
    s = get_settings()
    if s.fila_sincrona:
        # Modo de teste: processa na hora, repetindo em caso de falha temporária
        from app.processamento import FalhaTemporaria, processar_foto

        for foto_id in ids:
            for _ in range(s.max_tentativas):
                try:
                    processar_foto(foto_id)
                    break
                except FalhaTemporaria:
                    continue
        return

    q = fila()
    retentativas = max(0, s.max_tentativas - 1)
    for foto_id in ids:
        q.enqueue(
            "app.processamento.processar_foto",
            foto_id,
            job_timeout=600,
            # Em caso de falha temporária, tenta de novo depois de 15 s e 60 s
            retry=Retry(max=retentativas, interval=[15, 60]) if retentativas else None,
            description=f"Processar foto {foto_id}",
        )


FILA_EXPORTACOES = "exportacoes"


def enfileirar_exportacao(exportacao_id: str) -> None:
    """Gera o ZIP no worker (fila separada: um ZIP grande não atrasa as fotos)."""
    if get_settings().fila_sincrona:
        from app.exportacao import gerar_exportacao

        gerar_exportacao(exportacao_id)
        return
    fila(FILA_EXPORTACOES).enqueue(
        "app.exportacao.gerar_exportacao",
        exportacao_id,
        job_timeout=3600,
        description=f"Exportar {exportacao_id}",
    )
