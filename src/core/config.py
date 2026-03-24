"""Configuration management for MCP Weather Server."""

from __future__ import annotations

import os
import sys
import logging

logger = logging.getLogger(__name__)


class WeatherConfig:
    """CWA API and cache configuration."""

    def __init__(self):
        self.api_key = os.getenv("CWA_API_KEY", "")
        self.cache_ttl_hours = int(os.getenv("CACHE_TTL_HOURS", "24"))

        if not self.api_key:
            logger.error("CWA_API_KEY environment variable is required")
            sys.exit(1)


class HTTPConfig:
    """HTTP server configuration."""

    def __init__(self):
        self.host = os.getenv("HTTP_HOST", "0.0.0.0")
        self.port = int(os.getenv("HTTP_PORT", "8000"))
        self.cors_preflight_max_age = 600

    @property
    def cors_allowed_origins(self) -> list[str]:
        cors_env = os.getenv("CORS_ALLOWED_ORIGINS", "")
        if cors_env:
            return [origin.strip() for origin in cors_env.split(",")]
        environment = os.getenv("ENVIRONMENT", "development")
        if environment == "development":
            return ["http://localhost:3000", "http://localhost:8000"]
        return []


def get_weather_config() -> WeatherConfig:
    return WeatherConfig()


def get_http_config() -> HTTPConfig:
    return HTTPConfig()
