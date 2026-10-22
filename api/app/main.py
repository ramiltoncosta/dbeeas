"""
DBeeAS - API de detecção de abelhas pela asa.

Recebe a foto de uma asa, roda o modelo YOLO e devolve a espécie
mais provável, a confiança e as caixas detectadas.
"""

import base64
import io
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from PIL import Image, UnidentifiedImageError
from ultralytics import YOLO

# Configurações (podem ser alteradas por variáveis de ambiente)
MODEL_PATH = os.getenv("MODEL_PATH", "/models/best.pt")
MIN_CONFIDENCE = float(os.getenv("MIN_CONFIDENCE", "0.50"))  # abaixo disso: "não identificada"
DETECT_CONFIDENCE = float(os.getenv("DETECT_CONFIDENCE", "0.25"))  # limiar mínimo do YOLO
IMG_SIZE = int(os.getenv("IMG_SIZE", "640"))
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "15"))

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}

model: YOLO | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Carrega o modelo uma única vez, quando a API inicia
    global model
    if not os.path.exists(MODEL_PATH):
        raise RuntimeError(f"Modelo não encontrado em {MODEL_PATH}")
    model = YOLO(MODEL_PATH)
    yield


app = FastAPI(
    title="DBeeAS API",
    description="Sistema inteligente de reconhecimento de abelhas pela asa",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
def health():
    """Verifica se a API está no ar e se o modelo foi carregado."""
    return {
        "status": "ok",
        "modelo_carregado": model is not None,
        "especies": list(model.names.values()) if model else [],
    }


def _run_detection(image: Image.Image, annotate: bool) -> dict:
    result = model.predict(
        image, conf=DETECT_CONFIDENCE, imgsz=IMG_SIZE, verbose=False
    )[0]

    detections = []
    for box in result.boxes:
        class_id = int(box.cls)
        x1, y1, x2, y2 = (round(v, 1) for v in box.xyxy[0].tolist())
        detections.append(
            {
                "especie": model.names[class_id],
                "classe_id": class_id,
                "confianca": round(float(box.conf), 4),
                "caixa": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
            }
        )

    detections.sort(key=lambda d: d["confianca"], reverse=True)
    best = detections[0] if detections else None
    identified = best is not None and best["confianca"] >= MIN_CONFIDENCE

    response = {
        "identificada": identified,
        "especie": best["especie"] if identified else None,
        "confianca": best["confianca"] if best else None,
        "mensagem": None
        if identified
        else "Não foi possível identificar a espécie. Tente outra foto da asa.",
        "deteccoes": detections,
        "imagem": {"largura": image.width, "altura": image.height},
    }

    if annotate:
        # result.plot() devolve a imagem com as caixas (BGR); convertemos para RGB
        annotated = Image.fromarray(result.plot()[..., ::-1])
        buffer = io.BytesIO()
        annotated.save(buffer, format="JPEG", quality=85)
        response["imagem_anotada"] = base64.b64encode(buffer.getvalue()).decode()

    return response


@app.post("/detect")
async def detect(
    file: UploadFile = File(..., description="Foto da asa (JPEG, PNG ou WEBP)"),
    annotate: bool = Query(False, description="Devolver a imagem com as caixas desenhadas"),
):
    """Identifica a espécie da abelha a partir da foto da asa."""
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(415, "Formato não suportado. Envie JPEG, PNG ou WEBP.")

    data = await file.read()
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"Arquivo maior que {MAX_UPLOAD_MB} MB.")

    try:
        image = Image.open(io.BytesIO(data)).convert("RGB")
    except UnidentifiedImageError:
        raise HTTPException(400, "Não foi possível abrir a imagem.")

    # A inferência é pesada: roda fora do loop principal para não travar a API
    return await run_in_threadpool(_run_detection, image, annotate)
