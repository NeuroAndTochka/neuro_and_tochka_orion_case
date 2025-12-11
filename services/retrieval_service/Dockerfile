FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY retrieval_service ./retrieval_service

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

EXPOSE 8040

CMD ["uvicorn", "retrieval_service.main:app", "--host", "0.0.0.0", "--port", "8040"]
