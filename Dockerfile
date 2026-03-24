# MCP Weather Server - Multi-stage build

FROM python:3.11-slim AS base

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src/ ./src/

RUN pip install --no-cache-dir setuptools wheel && \
    pip install --no-cache-dir .

# Development stage
FROM base AS development

RUN pip install --no-cache-dir -e .

ENV PYTHONPATH="/app/src"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD ["python", "-m", "server"]

# Production stage
FROM base AS production

RUN pip install --no-cache-dir -e .

RUN useradd --create-home --shell /bin/bash mcpuser && \
    chown -R mcpuser:mcpuser /app

USER mcpuser

ENV PYTHONPATH="/app/src"
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "server"]
