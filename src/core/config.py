"""Configuration management for MCP Weather Server."""

from __future__ import annotations

import os
import logging

logger = logging.getLogger(__name__)


class WeatherConfig:
    """CWA API and cache configuration."""

    def __init__(self):
        self.api_key = os.getenv("CWA_API_KEY", "")
        self.cache_ttl_hours = int(os.getenv("CACHE_TTL_HOURS", "24"))

        # Deliberately does NOT sys.exit on a missing key.
        #
        # This process sits behind MCPO, which declares
        # `depends_on: mcp-weather-http: condition: service_healthy`. Exiting here
        # made the container unhealthy, that condition never became true, and MCPO
        # never started -- so a missing weather key took down *every* module's tools
        # (81 of them), not just this one. A per-module misconfiguration must not be
        # able to do that.
        #
        # Instead the server starts, `/` reports degraded, and the tools return an
        # explicit configuration error when called. The trade-off is deliberate: a
        # misconfigured module now starts "healthy" while being non-functional, so
        # the failure has to be visible in the tool response rather than at startup.
        if not self.api_key:
            logger.error(
                "CWA_API_KEY is not set -- weather tools will return a configuration "
                "error. The server still starts so that MCPO (and every other "
                "module's tools) stay available."
            )

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)


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


class MCPSecurityConfig:
    """MCP transport security configuration."""

    def __init__(self):
        self.enable_dns_rebinding_protection = (
            os.getenv("MCP_ENABLE_DNS_PROTECTION", "false").lower() == "true"
        )


def get_weather_config() -> WeatherConfig:
    return WeatherConfig()


def get_http_config() -> HTTPConfig:
    return HTTPConfig()


def get_mcp_security_config() -> MCPSecurityConfig:
    return MCPSecurityConfig()
