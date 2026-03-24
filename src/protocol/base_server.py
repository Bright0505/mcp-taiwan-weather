"""Base MCP server - transport-agnostic protocol implementation."""

import logging
from mcp.server import Server

from tools.definitions import WEATHER_TOOLS, handle_tool_call
from weather.cwa_client import CwaClient

logger = logging.getLogger(__name__)


class BaseMCPServer:
    """Base MCP server with weather tool handlers, independent of transport."""

    def __init__(self, cwa_client: CwaClient, server_name: str = "mcp-weather"):
        self.cwa_client = cwa_client
        self.server = Server(server_name)
        self._setup_handlers()
        logger.info(f"Initialized {server_name} MCP server")

    def _setup_handlers(self) -> None:
        @self.server.list_tools()
        async def list_tools():
            return WEATHER_TOOLS

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict):
            return await handle_tool_call(name, arguments or {}, self.cwa_client)

        @self.server.list_prompts()
        async def list_prompts():
            return []

        @self.server.list_resources()
        async def list_resources():
            return []
