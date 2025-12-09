FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY api_gateway ./api_gateway

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

EXPOSE 8080

CMD ["uvicorn", "api_gateway.main:app", "--host", "0.0.0.0", "--port", "8080"]
