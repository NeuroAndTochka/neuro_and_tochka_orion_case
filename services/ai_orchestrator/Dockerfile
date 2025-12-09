FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY ai_orchestrator ./ai_orchestrator

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

EXPOSE 8070

CMD ["uvicorn", "ai_orchestrator.main:app", "--host", "0.0.0.0", "--port", "8070"]
