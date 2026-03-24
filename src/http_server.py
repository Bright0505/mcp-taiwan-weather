"""HTTP/SSE mode standalone entry point.

Usage:
    python -m http_server
"""

import asyncio
import logging
import os

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def run_http_server() -> None:
    from main import run_http_mode

    host = os.getenv("HTTP_HOST", "0.0.0.0")
    port = int(os.getenv("HTTP_PORT", "8000"))
    asyncio.run(run_http_mode(host, port))


if __name__ == "__main__":
    run_http_server()
