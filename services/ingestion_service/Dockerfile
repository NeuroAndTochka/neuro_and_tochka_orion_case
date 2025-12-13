FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=600 \
    PIP_RETRIES=10 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY ingestion_service ./ingestion_service

RUN pip install --no-cache-dir .

EXPOSE 8050

CMD ["uvicorn", "ingestion_service.main:app", "--host", "0.0.0.0", "--port", "8050"]
