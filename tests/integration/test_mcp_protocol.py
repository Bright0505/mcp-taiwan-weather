"""MCP 協議層回歸測試（mcp-weather）。

存在理由
--------
本模組在此之前**完全沒有 `tests/` 目錄**，因此 MCP 2026-07-28 遷移時沒有任何安全網
—— 這也是它被排在 8 個資料庫模組之後才遷移的原因。

與資料庫模組的差異
------------------
* 只有 2 支工具，且不連資料庫（打中央氣象署 API），因此外部依賴以 `CwaClient` mock 掉
* 協議層在 `protocol/base_server.py` 的 `BaseMCPServer`，transport 子類繼承它
* `handle_tool_call()` 直接回傳 `list[TextContent]`（比資料庫模組更貼著 SDK 型別）

分層設計與資料庫模組一致：
1. 工具清單 / schema 形狀 / dispatch（不經 HTTP）
2. SDK wiring（handler 是否掛上 Server、transport 型別）
3. 兩個協議世代的相容性（真正打 `/mcp` endpoint）
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_types.version import HANDSHAKE_PROTOCOL_VERSIONS

from tools.definitions import WEATHER_TOOLS, handle_tool_call

EXPECTED_TOOLS = {"get_weekly_forecast", "list_counties"}

PROTOCOL_VERSION_META = "io.modelcontextprotocol/protocolVersion"
CLIENT_INFO_META = "io.modelcontextprotocol/clientInfo"
CLIENT_CAPABILITIES_META = "io.modelcontextprotocol/clientCapabilities"
MODERN_VERSION = "2026-07-28"
HANDSHAKE_VERSION = "2025-11-25"
_ACCEPT = "application/json, text/event-stream"


def _schema(tool):
    """同時支援 SDK v1 的 `inputSchema` 與 v2 的 `input_schema`。"""
    return getattr(tool, "input_schema", None) or tool.inputSchema


@pytest.fixture
def cwa_client():
    """mock 掉中央氣象署 client，測試不對外連網。"""
    client = MagicMock()
    client.get_weekly_forecast = AsyncMock(
        return_value={"error": False, "forecast": "臺北市 未來一週：晴時多雲"}
    )
    return client


# =============================================================================
# 第 1 層：工具清單 / schema / dispatch
# =============================================================================


class TestToolInventory:
    def test_expected_tools(self):
        assert {t.name for t in WEATHER_TOOLS} == EXPECTED_TOOLS

    def test_tool_names_are_unique(self):
        names = [t.name for t in WEATHER_TOOLS]
        assert len(names) == len(set(names))

    def test_every_tool_has_description(self):
        for tool in WEATHER_TOOLS:
            assert tool.description and tool.description.strip(), tool.name


class TestInputSchema:
    def test_schema_is_object_with_properties(self):
        for tool in WEATHER_TOOLS:
            schema = _schema(tool)
            assert schema["type"] == "object", tool.name
            assert isinstance(schema.get("properties"), dict), tool.name

    def test_every_property_declares_a_type(self):
        for tool in WEATHER_TOOLS:
            for prop_name, prop in _schema(tool)["properties"].items():
                assert "type" in prop, f"{tool.name}.{prop_name}"

    def test_array_properties_declare_items(self):
        """JSON Schema 2020-12 就緒度：array 缺 items 會退化成「任意型別的 list」。"""
        for tool in WEATHER_TOOLS:
            for prop_name, prop in _schema(tool)["properties"].items():
                if prop.get("type") == "array":
                    assert "items" in prop, f"{tool.name}.{prop_name} 缺 items"

    def test_no_external_schema_refs(self):
        """SEP-2106 安全要求：不得自動解析外部 `$ref` URI。"""

        def walk(node, path):
            if isinstance(node, dict):
                ref = node.get("$ref")
                if isinstance(ref, str):
                    assert ref.startswith("#"), f"{path}: 外部 $ref «{ref}»"
                for k, v in node.items():
                    walk(v, f"{path}.{k}")
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk(v, f"{path}[{i}]")

        for tool in WEATHER_TOOLS:
            walk(_schema(tool), tool.name)

    def test_forecast_tool_requires_county(self):
        tool = next(t for t in WEATHER_TOOLS if t.name == "get_weekly_forecast")
        schema = _schema(tool)
        assert schema["properties"]["county"]["type"] == "string"
        assert schema["properties"]["district"]["type"] == "string"
        assert schema["required"] == ["county"]


class TestDispatch:
    async def test_list_counties_returns_counties(self, cwa_client):
        content = await handle_tool_call("list_counties", {}, cwa_client)
        assert content
        assert "縣市" in content[0].text

    async def test_forecast_passes_arguments_through(self, cwa_client):
        content = await handle_tool_call(
            "get_weekly_forecast", {"county": "臺北市", "district": "中山區"}, cwa_client
        )
        cwa_client.get_weekly_forecast.assert_awaited_once_with("臺北市", "中山區")
        assert "晴時多雲" in content[0].text

    async def test_forecast_without_county_is_rejected(self, cwa_client):
        content = await handle_tool_call("get_weekly_forecast", {}, cwa_client)
        assert "county" in content[0].text
        cwa_client.get_weekly_forecast.assert_not_awaited()

    async def test_unknown_tool_is_reported(self, cwa_client):
        content = await handle_tool_call("no_such_tool", {}, cwa_client)
        assert "Unknown tool" in content[0].text

    async def test_upstream_error_is_surfaced(self, cwa_client):
        cwa_client.get_weekly_forecast = AsyncMock(
            return_value={"error": True, "message": "CWA API 無回應"}
        )
        content = await handle_tool_call("get_weekly_forecast", {"county": "臺北市"}, cwa_client)
        assert "CWA API 無回應" in content[0].text


# =============================================================================
# 第 2 層：SDK wiring
# =============================================================================


class TestProtocolWiring:
    @pytest.fixture
    def server(self, cwa_client):
        from protocol.streamable_server import StreamableMCPServer

        return StreamableMCPServer(cwa_client)

    def test_handlers_are_bound_to_instance(self, server):
        for name in ("_on_list_tools", "_on_call_tool", "_on_list_prompts", "_on_list_resources"):
            handler = getattr(server, name, None)
            assert callable(handler), f"{name} 不存在"
            assert handler.__self__ is server, f"{name} 未綁定到本實例"

    def test_streamable_http_transport_is_used(self, server):
        from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

        assert isinstance(server.session_manager, StreamableHTTPSessionManager)
        assert not hasattr(server, "sse_transport"), "SSE transport 應已移除"

    def test_cache_hints_are_configured(self, server):
        from mcp.server.caching import CacheHint

        hints = getattr(server.server, "cache_hints", None)
        assert hints and "tools/list" in hints
        assert isinstance(hints["tools/list"], CacheHint)
        assert hints["tools/list"].ttl_ms > 0

    async def test_on_list_tools_returns_typed_result(self, server):
        import mcp_types as types

        result = await server._on_list_tools(None, None)
        assert isinstance(result, types.ListToolsResult)
        assert {t.name for t in result.tools} == EXPECTED_TOOLS

    async def test_on_call_tool_returns_typed_result(self, server):
        import mcp_types as types

        params = types.CallToolRequestParams(name="list_counties", arguments={})
        result = await server._on_call_tool(None, params)

        assert isinstance(result, types.CallToolResult)
        assert result.content
        assert isinstance(result.content[0], types.TextContent)


# =============================================================================
# 第 3 層：兩個協議世代的相容性
# =============================================================================


class TestTwoEraCompatibility:
    """同一個 `/mcp` endpoint 必須同時服務兩個協議世代。

    第 1、2 層都不經過 HTTP，抓不到 transport 設定錯誤；本層真正打 endpoint。
    """

    @pytest.fixture
    def client(self, cwa_client):
        from fastapi.testclient import TestClient

        # main.run_http_mode 會直接啟動 uvicorn，因此這裡自行組出等價的 app，
        # 但沿用生產程式碼的 StreamableMCPServer 與 mount 路徑。
        import contextlib

        from fastapi import FastAPI

        from protocol.streamable_server import StreamableMCPServer

        mcp_server = StreamableMCPServer(cwa_client)

        @contextlib.asynccontextmanager
        async def lifespan(_app: FastAPI):
            async with mcp_server.session_manager.run():
                yield

        app = FastAPI(lifespan=lifespan)
        app.mount("/mcp", mcp_server.create_asgi_app())

        with TestClient(app) as c:
            yield c

    @staticmethod
    def _modern_body(method, params=None):
        return {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": {
                **(params or {}),
                "_meta": {
                    PROTOCOL_VERSION_META: MODERN_VERSION,
                    CLIENT_INFO_META: {"name": "pytest", "version": "1.0"},
                    CLIENT_CAPABILITIES_META: {},
                },
            },
        }

    @staticmethod
    def _modern_headers(method, tool_name=None):
        h = {
            "Accept": _ACCEPT,
            "Content-Type": "application/json",
            "MCP-Protocol-Version": MODERN_VERSION,
            "Mcp-Method": method,
        }
        if tool_name:
            h["Mcp-Name"] = tool_name
        return h

    def test_modern_list_tools(self, client):
        r = client.post(
            "/mcp/", json=self._modern_body("tools/list"),
            headers=self._modern_headers("tools/list"),
        )
        assert r.status_code == 200, r.text
        assert {t["name"] for t in r.json()["result"]["tools"]} == EXPECTED_TOOLS

    def test_modern_call_tool(self, client):
        r = client.post(
            "/mcp/",
            json=self._modern_body("tools/call", {"name": "list_counties", "arguments": {}}),
            headers=self._modern_headers("tools/call", "list_counties"),
        )
        assert r.status_code == 200, r.text
        assert r.json()["result"]["content"]

    def test_list_result_advertises_cache_hint(self, client):
        r = client.post(
            "/mcp/", json=self._modern_body("tools/list"),
            headers=self._modern_headers("tools/list"),
        )
        assert r.status_code == 200, r.text
        result = r.json()["result"]

        expected_ms = int(os.getenv("MCP_LIST_CACHE_TTL_SECONDS", "300")) * 1000
        assert result.get("ttlMs") == expected_ms
        assert result["ttlMs"] <= 3600 * 1000, (
            "客戶端快取無法遠端失效，advertised TTL 不應超過 1 小時"
        )

    def test_modern_requires_mcp_method_header(self, client):
        """斷言確切的 400 與 -32020：只寫 `>= 400` 的話，endpoint 不存在時的 404 也會通過。"""
        headers = self._modern_headers("tools/list")
        del headers["Mcp-Method"]

        r = client.post("/mcp/", json=self._modern_body("tools/list"), headers=headers)

        assert r.status_code == 400, f"缺少 Mcp-Method 應回 400，實際 {r.status_code}"
        assert r.json()["error"]["code"] == -32020

    def test_modern_requires_meta_envelope(self, client):
        body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}

        r = client.post("/mcp/", json=body, headers=self._modern_headers("tools/list"))

        assert r.status_code == 400
        assert r.json()["error"]["code"] == -32602

    def _handshake_init(self, client):
        return client.post(
            "/mcp/",
            json={
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {
                    "protocolVersion": HANDSHAKE_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "1.0"},
                },
            },
            headers={"Accept": _ACCEPT, "Content-Type": "application/json"},
        )

    def test_handshake_initialize_succeeds(self, client):
        r = self._handshake_init(client)
        assert r.status_code == 200, r.text
        assert r.json()["result"]["protocolVersion"] in HANDSHAKE_PROTOCOL_VERSIONS

    def test_both_eras_advertise_the_same_tools(self, client):
        """部署真正依賴的不變量：MCPO 走 handshake、新客戶端走 2026-07-28，
        兩邊看到的能力必須一致。"""
        modern = client.post(
            "/mcp/", json=self._modern_body("tools/list"),
            headers=self._modern_headers("tools/list"),
        )
        assert modern.status_code == 200, modern.text

        init = self._handshake_init(client)
        assert init.status_code == 200
        headers = {"Accept": _ACCEPT, "Content-Type": "application/json"}
        sid = init.headers.get("mcp-session-id")
        if sid:
            headers["mcp-session-id"] = sid
        handshake = client.post(
            "/mcp/", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            headers=headers,
        )
        assert handshake.status_code == 200, handshake.text

        assert {t["name"] for t in modern.json()["result"]["tools"]} == {
            t["name"] for t in handshake.json()["result"]["tools"]
        }
