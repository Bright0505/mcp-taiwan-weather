"""Unified entry point for MCP Weather Server.

Usage:
    python main.py          # STDIO mode (default)
    python main.py --http   # HTTP mode (MCP over Streamable HTTP)
    python main.py --http --host 0.0.0.0 --port 8000
"""

import asyncio
import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _build_cwa_client():
    from dotenv import load_dotenv
    load_dotenv()

    from core.config import WeatherConfig
    from weather.cache import TtlCache
    from weather.cwa_client import CwaClient

    config = WeatherConfig()
    cache = TtlCache(ttl_hours=config.cache_ttl_hours)
    return CwaClient(api_key=config.api_key, cache=cache)


async def run_stdio_mode() -> None:
    logger.info("Starting MCP Weather Server in STDIO mode")
    from protocol.stdio_server import run_stdio_server

    cwa_client = _build_cwa_client()
    try:
        await run_stdio_server(cwa_client)
    except Exception as e:
        logger.error(f"STDIO server error: {e}", exc_info=True)
        sys.exit(1)


async def run_http_mode(host: str = "0.0.0.0", port: int = 8000) -> None:
    logger.info(f"Starting MCP Weather Server in HTTP mode on {host}:{port}")

    import contextlib

    import uvicorn
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from protocol.streamable_server import StreamableMCPServer

    cwa_client = _build_cwa_client()
    mcp_server = StreamableMCPServer(cwa_client)

    @contextlib.asynccontextmanager
    async def lifespan(_app: FastAPI):
        # StreamableHTTPSessionManager must be running for the endpoint to serve.
        async with mcp_server.session_manager.run():
            yield

    app = FastAPI(
        title="MCP Weather API",
        version="1.0.0",
        description=(
            "台灣一週天氣預報 MCP Server。\n\n"
            "## MCP Tools\n"
            "透過 Streamable HTTP 端點（`/mcp/`）提供以下 MCP tools：\n\n"
            "| Tool | 說明 | 參數 |\n"
            "|------|------|------|\n"
            "| `get_weekly_forecast` | 取得一週天氣預報 | `county`（必填）、`district`（選填）|\n"
            "| `list_counties` | 列出所有可查詢縣市 | 無 |\n\n"
            "## 快取\n"
            "每個縣市的查詢結果快取 24 小時，期間不重複呼叫 CWA API。\n\n"
            "## 協議世代\n"
            "同一個端點同時服務 initialize handshake 世代與無狀態的 2026-07-28 世代。"
        ),
        lifespan=lifespan,
    )

    # MCP 2026-07-28 (SEP-2243) requires Mcp-Method / Mcp-Name on requests and uses
    # MCP-Protocol-Version to carry the era; a browser client cannot send them unless
    # the preflight allows them. Replaces the hand-written CORS handling that lived in
    # the old SSE ASGI app.
    _cors_env = os.getenv("CORS_ALLOWED_ORIGINS", "")
    if _cors_env:
        _allowed_origins = [o.strip() for o in _cors_env.split(",")]
    elif os.getenv("ENVIRONMENT", "development") == "development":
        _allowed_origins = ["http://localhost:3000", "http://localhost:8000"]
        logger.info("使用開發環境 CORS 預設值")
    else:
        _allowed_origins = []
        logger.warning("生產環境未設定 CORS_ALLOWED_ORIGINS，CORS 已停用")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "Mcp-Method",
            "Mcp-Name",
            "MCP-Protocol-Version",
            "Mcp-Session-Id",
        ],
    )

    @app.get("/", summary="伺服器資訊", tags=["General"])
    async def root():
        """回傳伺服器基本資訊與可用端點列表。"""
        return {
            "name": "MCP Weather Server",
            "version": "1.0.0",
            "endpoints": {
                "health": "/health",
                "mcp": "/mcp/",
                "docs": "/docs",
            },
        }

    @app.get("/health", summary="健康檢查", tags=["General"])
    async def health():
        """Docker healthcheck 用端點，回傳服務狀態。"""
        return {"status": "ok", "service": "mcp-weather"}

    app.mount("/mcp", mcp_server.create_asgi_app())
    logger.info("MCP server mounted at /mcp/ (Streamable HTTP, dual-era)")

    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    try:
        await server.serve()
    except Exception as e:
        logger.error(f"HTTP server error: {e}", exc_info=True)
        sys.exit(1)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="MCP Weather Server")
    parser.add_argument(
        "--http",
        action="store_true",
        help="Run in HTTP mode (MCP over Streamable HTTP at /mcp/ + REST)",
    )
    parser.add_argument("--host", type=str, default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    if args.http:
        host = args.host or os.getenv("HTTP_HOST", "0.0.0.0")
        port = args.port or int(os.getenv("HTTP_PORT", "8000"))
        asyncio.run(run_http_mode(host, port))
    else:
        asyncio.run(run_stdio_mode())


if __name__ == "__main__":
    main()
