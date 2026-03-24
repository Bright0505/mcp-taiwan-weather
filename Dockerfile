# MCP Weather Server - Multi-stage build

FROM python:3.11-slim AS base

WORKDIR /app

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

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import mcp; print('OK')" || exit 1

CMD ["python", "-m", "server"]
