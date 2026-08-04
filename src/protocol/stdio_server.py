"""STDIO transport MCP server."""

from __future__ import annotations

import logging

from mcp.server.runner import serve_dual_era_loop
from mcp.server.stdio import stdio_server

from protocol.base_server import BaseMCPServer
from weather.cwa_client import CwaClient

logger = logging.getLogger(__name__)


class StdioMCPServer(BaseMCPServer):
    """MCP server using STDIO transport."""

    async def run(self) -> None:
        logger.info("Starting STDIO MCP server")
        # serve_dual_era_loop serves both the initialize-handshake era and the stateless
        # 2026-07-28 era. lifespan_state is a required keyword argument, so the server
        # lifespan has to be entered first to obtain it.
        async with self.server.lifespan(self.server) as lifespan_state:
            async with stdio_server() as (read_stream, write_stream):
                await serve_dual_era_loop(
                    self.server,
                    read_stream,
                    write_stream,
                    lifespan_state=lifespan_state,
                )


async def run_stdio_server(cwa_client: CwaClient) -> None:
    server = StdioMCPServer(cwa_client)
    await server.run()
