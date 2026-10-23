FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
# Em desenvolvimento instala também as ferramentas de teste
ARG DEV=false
RUN pip install --no-cache-dir -r $([ "$DEV" = "true" ] && echo requirements-dev.txt || echo requirements.txt)

COPY . .

# Pasta das fotos: criada aqui para o volume do Docker já nascer com o dono certo
RUN useradd --create-home dbeeas && mkdir -p /data/arquivos && chown -R dbeeas /app /data/arquivos
USER dbeeas

EXPOSE 8000
# Aplica as migrações do banco e inicia a API
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
