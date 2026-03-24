"""STDIO mode standalone entry point.

Usage:
    python -m server
"""

import asyncio
import logging

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

from core.config import WeatherConfig
from weather.cache import TtlCache
from weather.cwa_client import CwaClient
from protocol.stdio_server import run_stdio_server


def main() -> None:
    config = WeatherConfig()
    cache = TtlCache(ttl_hours=config.cache_ttl_hours)
    cwa_client = CwaClient(api_key=config.api_key, cache=cache)
    asyncio.run(run_stdio_server(cwa_client))


if __name__ == "__main__":
    main()
