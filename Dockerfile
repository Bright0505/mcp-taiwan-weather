# MCP Weather Server - Multi-stage build

FROM python:3.11-slim AS base

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml constraints.txt ./
COPY src/ ./src/

# constraints.txt pins every transitive dependency version so a rebuild resolves the
# same tree. The version ranges in pyproject.toml still allow drift inside their bounds
# (an earlier rebuild moved mcp 1.28.1 -> 1.29.0 with no code change), which is exactly
# how an unnoticed upgrade reaches production. Regenerate with `pip freeze` inside a
# built image when dependencies change intentionally.
RUN pip install --no-cache-dir setuptools wheel && \
    pip install --no-cache-dir -c constraints.txt .

# Development stage
FROM base AS development

RUN pip install --no-cache-dir -c constraints.txt -e ".[dev]"

ENV PYTHONPATH="/app/src"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD ["python", "-m", "server"]

# Production stage
FROM base AS production

RUN pip install --no-cache-dir -c constraints.txt -e .

RUN useradd --create-home --shell /bin/bash mcpuser && \
    chown -R mcpuser:mcpuser /app

USER mcpuser

ENV PYTHONPATH="/app/src"
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "server"]
