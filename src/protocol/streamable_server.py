"""Streamable HTTP transport MCP server.

Replaces the previous SSE transport. One endpoint serves both protocol eras -- the
`initialize` handshake era (up to 2025-11-25) and the stateless 2026-07-28 era -- so
existing clients keep working while 2026-07-28 clients are also accepted. Era
selection, method routing and the Mcp-Method / Mcp-Name / MCP-Protocol-Version header
requirements are handled by the SDK, which is why the hand-written ASGI dispatch and
CORS injection this file used to carry are gone. CORS is now applied by the standard
FastAPI middleware in main.py.
"""

from __future__ import annotations

import logging

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings

from core.config import get_mcp_security_config
from protocol.base_server import BaseMCPServer
from weather.cwa_client import CwaClient

logger = logging.getLogger(__name__)


class StreamableMCPServer(BaseMCPServer):
    """MCP server using Streamable HTTP transport."""

    def __init__(self, cwa_client: CwaClient):
        super().__init__(cwa_client)
        security_config = get_mcp_security_config()
        security_settings = TransportSecuritySettings(
            enable_dns_rebinding_protection=security_config.enable_dns_rebinding_protection
        )
        # stateless=True matches the 2026-07-28 stateless model and keeps the handshake
        # era working; with no server-side session there is nothing to pin a client to,
        # so no sticky routing is needed in front of this service.
        self.session_manager = StreamableHTTPSessionManager(
            app=self.server,
            stateless=True,
            json_response=True,
            security_settings=security_settings,
        )
        logger.info("Streamable HTTP MCP server initialized")

    def create_asgi_app(self):
        """Create the ASGI app to mount; the SDK handles all routing."""

        async def app(scope, receive, send):
            await self.session_manager.handle_request(scope, receive, send)

        return app
