"""STDIO transport MCP server."""

from __future__ import annotations

import logging
from mcp.server.stdio import stdio_server

from protocol.base_server import BaseMCPServer
from weather.cwa_client import CwaClient

logger = logging.getLogger(__name__)


class StdioMCPServer(BaseMCPServer):
    """MCP server using STDIO transport."""

    async def run(self) -> None:
        logger.info("Starting STDIO MCP server")
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )


async def run_stdio_server(cwa_client: CwaClient) -> None:
    server = StdioMCPServer(cwa_client)
    await server.run()
