# Optional AeroFox app image. Supply a project-controlled loopback model in the
# same network namespace, or set AEROFOX_LLM=off for an evidence-only image.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    AEROFOX_PUBLIC_DEMO=1 AEROFOX_RATE_PER_MINUTE=12 AEROFOX_LLM_DAILY_TURNS=500
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY backend ./backend
COPY frontend ./frontend
COPY data/processed ./data/processed
COPY data/findings ./data/findings
COPY data/curated ./data/curated
COPY data/raw/ntrs ./data/raw/ntrs
COPY data/raw/psi/manifest.json ./data/raw/psi/manifest.json
COPY outputs/figures ./outputs/figures
RUN useradd -m aerofox && chown -R aerofox /app
USER aerofox
WORKDIR /app/backend
EXPOSE 7860
CMD ["sh", "-c", "uvicorn aerofox.api.app:app --host 0.0.0.0 --port ${PORT:-7860} --workers 1 --no-proxy-headers"]
