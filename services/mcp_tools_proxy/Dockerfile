FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY mcp_tools_proxy ./mcp_tools_proxy

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

EXPOSE 8082

CMD ["uvicorn", "mcp_tools_proxy.main:app", "--host", "0.0.0.0", "--port", "8082"]
