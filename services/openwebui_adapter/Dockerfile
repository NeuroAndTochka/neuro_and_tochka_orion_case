FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY openwebui_adapter ./openwebui_adapter

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

EXPOSE 8093

CMD ["uvicorn", "openwebui_adapter.main:app", "--host", "0.0.0.0", "--port", "8093"]
