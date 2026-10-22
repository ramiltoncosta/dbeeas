FROM python:3.12-slim

# Bibliotecas de sistema que o OpenCV (usado pela Ultralytics) precisa
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Roda como usuário comum, não como root
RUN useradd --create-home dbeeas
USER dbeeas

ENV YOLO_CONFIG_DIR=/tmp/ultralytics

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
