FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY ml_observer ./ml_observer

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

EXPOSE 8085

CMD ["uvicorn", "ml_observer.main:app", "--host", "0.0.0.0", "--port", "8085"]
