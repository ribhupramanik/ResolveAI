FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/home/appuser/.cache/huggingface \
    TOKENIZERS_PARALLELISM=false

WORKDIR /app

COPY requirements-prod.txt ./requirements-prod.txt

RUN python -m pip install --no-cache-dir -r requirements-prod.txt

RUN useradd --create-home --uid 10001 appuser

COPY --chown=appuser:appuser src ./src
COPY --chown=appuser:appuser data/knowledge ./data/knowledge
COPY --chown=appuser:appuser migrations ./migrations
COPY --chown=appuser:appuser alembic.ini ./alembic.ini

USER appuser

RUN python -c 'from sentence_transformers import SentenceTransformer; SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu")'

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]