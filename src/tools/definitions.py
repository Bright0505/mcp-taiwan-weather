"""MCP tool definitions and handlers for weather server."""

import logging
from mcp.types import Tool, TextContent

from weather.cwa_client import CwaClient
from weather.dataset_mapping import get_all_county_names

logger = logging.getLogger(__name__)

WEATHER_TOOLS = [
    Tool(
        name="get_weekly_forecast",
        description=(
            "取得台灣各縣市鄉鎮的未來一週天氣預報。"
            "Get 1-week weather forecast for a Taiwan county/city and optionally a specific district."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "county": {
                    "type": "string",
                    "description": (
                        "縣市名稱，例如：臺北市、新北市、桃園市。"
                        "County/city name in Chinese. Accepts 台/臺 variants and names without suffix."
                    ),
                },
                "district": {
                    "type": "string",
                    "description": (
                        "鄉鎮區名稱，例如：中山區、板橋區（可省略）。"
                        "Optional district/township name. If omitted, returns forecasts for all districts."
                    ),
                },
            },
            "required": ["county"],
        },
    ),
    Tool(
        name="list_counties",
        description=(
            "列出所有可查詢的台灣縣市名稱。"
            "List all available Taiwan counties/cities for weather queries."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
]


async def handle_tool_call(
    name: str, arguments: dict, cwa_client: CwaClient
) -> list[TextContent]:
    """Dispatch tool calls to the appropriate handler."""
    if name == "get_weekly_forecast":
        return await _handle_get_weekly_forecast(arguments, cwa_client)
    elif name == "list_counties":
        return _handle_list_counties()
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def _handle_get_weekly_forecast(
    arguments: dict, cwa_client: CwaClient
) -> list[TextContent]:
    county = arguments.get("county", "").strip()
    district = arguments.get("district", "").strip() or None

    if not county:
        return [TextContent(type="text", text="請提供縣市名稱（county 參數）")]

    result = await cwa_client.get_weekly_forecast(county, district)

    if result.get("error"):
        return [TextContent(type="text", text=result["message"])]

    return [TextContent(type="text", text=result["forecast"])]


def _handle_list_counties() -> list[TextContent]:
    counties = get_all_county_names()
    text = "台灣可查詢的縣市（共 {} 個）：\n{}".format(
        len(counties), "\n".join(f"  - {c}" for c in counties)
    )
    return [TextContent(type="text", text=text)]
