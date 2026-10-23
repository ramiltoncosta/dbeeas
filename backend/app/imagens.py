"""Leitura e validação de imagens: tipo real, EXIF (GPS e data) e miniaturas."""

import io
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from PIL import ExifTags, Image, ImageOps, UnidentifiedImageError

from app.config import get_settings

# Formatos aceitos, conferidos pelo conteúdo do arquivo (não pela extensão)
FORMATOS = {
    "JPEG": ("image/jpeg", "jpg"),
    "PNG": ("image/png", "png"),
    "WEBP": ("image/webp", "webp"),
}

# Evita imagens gigantes que travariam o servidor (ex.: 20.000 x 20.000 pixels)
Image.MAX_IMAGE_PIXELS = 60_000_000


class ImagemInvalida(ValueError):
    pass


@dataclass
class InfoImagem:
    tipo_mime: str
    extensao: str
    largura: int
    altura: int
    latitude: float | None
    longitude: float | None
    data_captura: datetime | None


def _para_graus(valor, ref) -> float | None:
    """Converte (graus, minutos, segundos) do EXIF para graus decimais."""
    try:
        g, m, s = (float(x) for x in valor)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    graus = g + m / 60 + s / 3600
    if isinstance(ref, bytes):
        ref = ref.decode(errors="ignore")
    if str(ref).strip().upper() in ("S", "W"):
        graus = -graus
    return graus


def _ler_exif(img: Image.Image) -> tuple[float | None, float | None, datetime | None]:
    try:
        exif = img.getexif()
    except Exception:
        return None, None, None

    lat = lon = None
    gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
    if gps:
        lat = _para_graus(gps.get(ExifTags.GPS.GPSLatitude), gps.get(ExifTags.GPS.GPSLatitudeRef))
        lon = _para_graus(gps.get(ExifTags.GPS.GPSLongitude), gps.get(ExifTags.GPS.GPSLongitudeRef))
        if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            lat = lon = None
        elif lat == 0 and lon == 0:  # alguns aparelhos gravam 0,0 quando não têm sinal
            lat = lon = None

    exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
    texto = exif_ifd.get(ExifTags.Base.DateTimeOriginal) or exif.get(ExifTags.Base.DateTime)
    fuso = _fuso(exif_ifd.get(ExifTags.Base.OffsetTimeOriginal))
    data = None
    if isinstance(texto, str):
        try:
            data = datetime.strptime(texto.strip(), "%Y:%m:%d %H:%M:%S").replace(tzinfo=fuso)
        except ValueError:
            data = None
    return lat, lon, data


def _fuso(offset) -> timezone | ZoneInfo:
    """Fuso da foto. Celulares recentes gravam (ex.: "-04:00"); senão, usa o fuso padrão."""
    if isinstance(offset, str) and len(offset.strip()) == 6:
        try:
            sinal = -1 if offset.strip()[0] == "-" else 1
            horas, minutos = (int(x) for x in offset.strip()[1:].split(":"))
            return timezone(sinal * timedelta(hours=horas, minutes=minutos))
        except ValueError:
            pass
    return ZoneInfo(get_settings().fuso_horario_padrao)


def analisar(dados: bytes) -> InfoImagem:
    """Confere se o arquivo é mesmo uma imagem aceita e lê os metadados."""
    try:
        with Image.open(io.BytesIO(dados)) as img:
            formato = img.format
            img.verify()  # detecta arquivos corrompidos
        with Image.open(io.BytesIO(dados)) as img:
            largura, altura = img.size
            if _orientacao(img) in (5, 6, 7, 8):  # foto "deitada": guardamos já girada
                largura, altura = altura, largura
            lat, lon, data = _ler_exif(img)
    except Image.DecompressionBombError as e:
        raise ImagemInvalida("Imagem grande demais.") from e
    except (UnidentifiedImageError, OSError, SyntaxError) as e:
        raise ImagemInvalida("O arquivo não é uma imagem válida.") from e

    if formato not in FORMATOS:
        raise ImagemInvalida("Formato não aceito. Envie JPEG, PNG ou WEBP.")
    mime, ext = FORMATOS[formato]
    return InfoImagem(mime, ext, largura, altura, lat, lon, data)


def _orientacao(img: Image.Image) -> int:
    try:
        return int(img.getexif().get(ExifTags.Base.Orientation, 1))
    except Exception:
        return 1


def preparar_para_detector(dados: bytes) -> tuple[bytes, str]:
    """Imagem enviada ao detector, com a rotação correta.

    Celulares gravam muitas fotos "deitadas" e indicam a rotação no EXIF. Girando antes,
    as caixas do modelo ficam na mesma posição da imagem mostrada no site.
    Fotos sem rotação vão como estão, sem perder qualidade.
    """
    with Image.open(io.BytesIO(dados)) as img:
        if _orientacao(img) == 1:
            return dados, Image.MIME.get(img.format, "image/jpeg")
        girada = ImageOps.exif_transpose(img).convert("RGB")
        saida = io.BytesIO()
        girada.save(saida, format="JPEG", quality=95)
        return saida.getvalue(), "image/jpeg"


def reduzir(dados: bytes, lado_maximo: int, qualidade: int = 82) -> bytes:
    """Gera uma versão menor em JPEG, já com a rotação correta."""
    with Image.open(io.BytesIO(dados)) as img:
        img = ImageOps.exif_transpose(img)
        img.thumbnail((lado_maximo, lado_maximo))
        if img.mode not in ("RGB", "L"):
            fundo = Image.new("RGB", img.size, (255, 255, 255))
            fundo.paste(img, mask=img.getchannel("A") if "A" in img.getbands() else None)
            img = fundo
        saida = io.BytesIO()
        img.save(saida, format="JPEG", quality=qualidade, optimize=True)
        return saida.getvalue()
