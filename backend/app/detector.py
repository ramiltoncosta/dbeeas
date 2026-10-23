"""Comunicação com o detector (a API do YOLO)."""

import httpx

from app.config import get_settings


class DetectorIndisponivel(RuntimeError):
    """O detector não respondeu. Vale tentar de novo mais tarde."""


class ImagemRecusada(ValueError):
    """O detector recusou a imagem. Tentar de novo não adianta."""


def detectar(dados: bytes, tipo_mime: str, nome: str, anotar: bool = False) -> dict:
    s = get_settings()
    try:
        r = httpx.post(
            f"{s.detector_url.rstrip('/')}/detect",
            params={"annotate": "true"} if anotar else None,
            files={"file": (nome, dados, tipo_mime)},
            timeout=s.detector_timeout_s,
        )
    except httpx.HTTPError as e:
        raise DetectorIndisponivel(f"Detector indisponível: {e.__class__.__name__}") from e

    if 400 <= r.status_code < 500:
        try:
            motivo = r.json().get("detail", "")
        except ValueError:
            motivo = r.text[:200]
        raise ImagemRecusada(f"Imagem recusada pelo detector: {motivo}")
    if r.status_code >= 500:
        raise DetectorIndisponivel(f"Erro no detector (HTTP {r.status_code})")
    return r.json()


def saude() -> dict:
    """Espécies reconhecidas e versão do modelo em uso."""
    s = get_settings()
    try:
        r = httpx.get(f"{s.detector_url.rstrip('/')}/health", timeout=10)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as e:
        raise DetectorIndisponivel("Detector indisponível") from e
