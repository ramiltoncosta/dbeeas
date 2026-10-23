"""Processamento das fotos, executado pelo worker (fora da requisição HTTP).

Para cada foto: gera miniaturas, envia ao detector e guarda o resultado.
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import detector
from app.armazenamento import get_armazenamento
from app.config import get_settings
from app.db import SessionLocal
from app.imagens import preparar_para_detector, reduzir
from app.models import Especie, Foto, Identificacao, ModeloIA, StatusFoto
from app.security import agora

log = logging.getLogger("dbeeas.processamento")

LADO_MINIATURA = 400
LADO_MEDIA = 1600


class FalhaTemporaria(RuntimeError):
    """Erro que pode passar sozinho (ex.: detector reiniciando). A fila tenta de novo."""


def _obter_ou_criar(db: Session, modelo, filtro: dict, **extra):
    obj = db.scalar(select(modelo).filter_by(**filtro))
    if obj:
        return obj
    try:
        with db.begin_nested():  # outro worker pode criar ao mesmo tempo
            obj = modelo(**filtro, **extra)
            db.add(obj)
        return obj
    except IntegrityError:
        return db.scalar(select(modelo).filter_by(**filtro))


def _registrar_modelo(db: Session, versao: str) -> ModeloIA:
    modelo = db.scalar(select(ModeloIA).where(ModeloIA.versao == versao))
    if modelo:
        return modelo
    # Modelo novo: cadastra as espécies que ele reconhece
    especies: list[str] = []
    try:
        especies = detector.saude().get("especies", [])
    except detector.DetectorIndisponivel:
        pass
    for nome in especies:
        _obter_ou_criar(db, Especie, {"nome_cientifico": nome})
    return _obter_ou_criar(db, ModeloIA, {"versao": versao}, especies=especies)


def _gerar_miniaturas(foto: Foto, dados: bytes) -> None:
    arm = get_armazenamento()
    base = foto.arquivo.rsplit(".", 1)[0]
    if not foto.miniatura:
        chave = f"{base}_mini.jpg"
        arm.salvar(chave, reduzir(dados, LADO_MINIATURA, qualidade=78))
        foto.miniatura = chave
    if not foto.media:
        chave = f"{base}_media.jpg"
        arm.salvar(chave, reduzir(dados, LADO_MEDIA, qualidade=85))
        foto.media = chave


def processar_foto(foto_id: str) -> str:
    """Tarefa da fila. Retorna o status final (útil nos testes e nos logs)."""
    max_tentativas = get_settings().max_tentativas
    with SessionLocal() as db:
        foto = db.get(Foto, uuid.UUID(foto_id))
        if foto is None:
            return "removida"  # a foto foi apagada enquanto esperava na fila
        if foto.status == StatusFoto.concluida:
            return foto.status.value

        foto.status = StatusFoto.processando
        foto.tentativas += 1
        db.commit()

        try:
            dados = get_armazenamento().ler(foto.arquivo)
            _gerar_miniaturas(foto, dados)
            db.commit()  # as miniaturas ficam salvas mesmo se o detector falhar
            corpo, mime = preparar_para_detector(dados)
            resultado = detector.detectar(corpo, mime, foto.nome_original)

            modelo = _registrar_modelo(db, resultado.get("versao_modelo") or "desconhecida")
            especie = None
            if resultado.get("especie"):
                especie = _obter_ou_criar(db, Especie, {"nome_cientifico": resultado["especie"]})
            db.add(
                Identificacao(
                    foto_id=foto.id,
                    modelo_id=modelo.id if modelo else None,
                    especie_id=especie.id if especie else None,
                    identificada=bool(resultado.get("identificada")),
                    confianca=resultado.get("confianca"),
                    deteccoes=resultado.get("deteccoes") or [],
                )
            )
            foto.status = StatusFoto.concluida
            foto.erro = None
            foto.processada_em = agora()
            db.commit()
            return foto.status.value

        except (detector.ImagemRecusada, FileNotFoundError) as e:
            # Não adianta tentar de novo
            db.rollback()
            foto.status = StatusFoto.erro
            foto.erro = str(e)[:500]
            db.commit()
            log.warning("Foto %s com erro definitivo: %s", foto_id, e)
            return foto.status.value

        except Exception as e:
            db.rollback()
            log.exception("Falha ao processar a foto %s (tentativa %s)", foto_id, foto.tentativas)
            if foto.tentativas >= max_tentativas:
                foto.status = StatusFoto.erro
                foto.erro = "Não foi possível processar a foto. Tente reprocessar mais tarde."
                db.commit()
                return foto.status.value
            foto.status = StatusFoto.na_fila
            db.commit()
            raise FalhaTemporaria(str(e)) from e
