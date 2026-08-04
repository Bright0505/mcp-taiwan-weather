"""Base MCP server - transport-agnostic protocol implementation."""

import logging
import os

import mcp_types as types
from mcp.server import Server
from mcp.server.caching import CacheHint

from tools.definitions import WEATHER_TOOLS, handle_tool_call
from weather.cwa_client import CwaClient

logger = logging.getLogger(__name__)


class BaseMCPServer:
    """Base MCP server with weather tool handlers, independent of transport."""

    def __init__(self, cwa_client: CwaClient, server_name: str = "mcp-weather"):
        self.cwa_client = cwa_client

        # SEP-2549: how long a client may cache list results. Kept short because a
        # client-side cache cannot be invalidated remotely, so this value is the
        # worst-case staleness window. This tool list is effectively static, so a short
        # TTL costs only an occasional extra tools/list round-trip.
        # scope="public": the tool list is identical for every caller (unlike the
        # database modules, whose descriptions embed a deployment-specific whitelist).
        list_cache_ttl_ms = int(os.getenv("MCP_LIST_CACHE_TTL_SECONDS", "300")) * 1000
        cache_hints = {
            "tools/list": CacheHint(ttl_ms=list_cache_ttl_ms, scope="public"),
            "prompts/list": CacheHint(ttl_ms=list_cache_ttl_ms, scope="public"),
            "resources/list": CacheHint(ttl_ms=list_cache_ttl_ms, scope="public"),
        }

        # Handlers are constructor arguments: the decorator API (@server.list_tools()
        # etc.) was removed in mcp SDK v2, and handlers must return typed Results
        # because automatic return-value wrapping is gone.
        self.server = Server(
            server_name,
            cache_hints=cache_hints,
            on_list_tools=self._on_list_tools,
            on_call_tool=self._on_call_tool,
            on_list_prompts=self._on_list_prompts,
            on_list_resources=self._on_list_resources,
        )
        logger.info(f"Initialized {server_name} MCP server")

    async def _on_list_tools(self, ctx, params) -> types.ListToolsResult:
        return types.ListToolsResult(tools=WEATHER_TOOLS)

    async def _on_call_tool(
        self, ctx, params: types.CallToolRequestParams
    ) -> types.CallToolResult:
        # handle_tool_call already returns list[TextContent]; v2 only needs it wrapped
        # in a typed result.
        content = await handle_tool_call(params.name, params.arguments or {}, self.cwa_client)
        return types.CallToolResult(content=list(content))

    async def _on_list_prompts(self, ctx, params) -> types.ListPromptsResult:
        return types.ListPromptsResult(prompts=[])

    async def _on_list_resources(self, ctx, params) -> types.ListResourcesResult:
        return types.ListResourcesResult(resources=[])
