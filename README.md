# mcp-taiwan-weather

台灣一週天氣預報 MCP Server，資料來源為[中央氣象署開放資料平台](https://opendata.cwa.gov.tw/)。

支援兩種運行模式：
- **STDIO 模式** — 直接整合 Claude Desktop
- **HTTP 模式（Streamable HTTP）** — 供 Open WebUI 原生 MCP 連線直連
  或任何支援 MCP Streamable HTTP 的客戶端整合

> **Transport**：2026-08-04 起改用 **Streamable HTTP**（端點 `/mcp/`），
> 取代舊的 SSE transport。`/sse/` 已不存在（回 404）。
> 同一個 `/mcp/` 端點同時服務 `initialize` handshake 世代與無狀態的
> **2026-07-28** 世代，世代判別由 MCP SDK 處理。

## 功能

- 查詢台灣 22 個縣市、各鄉鎮區的未來一週逐 12 小時天氣預報
- 提供溫度、體感溫度、降雨機率、相對濕度、風向風速、舒適度、紫外線指數、天氣描述
- 24 小時區域快取，同一縣市重複查詢不重複呼叫 API
- 自動正規化縣市名稱（台/臺 互換、省略市/縣後綴）

## 可查詢縣市

宜蘭縣、桃園市、新竹縣、苗栗縣、彰化縣、南投縣、雲林縣、嘉義縣、屏東縣、臺東縣、花蓮縣、澎湖縣、基隆市、新竹市、嘉義市、臺北市、高雄市、新北市、臺中市、臺南市、連江縣、金門縣

## MCP Tools

| Tool | 說明 | 參數 |
|------|------|------|
| `get_weekly_forecast` | 取得一週天氣預報 | `county`（必填）、`district`（選填）|
| `list_counties` | 列出所有可查詢縣市 | 無 |

### 使用範例

```
get_weekly_forecast(county="臺北市", district="中山區")
get_weekly_forecast(county="台北市")   # 台/臺 皆可
get_weekly_forecast(county="台北")     # 省略「市」亦可
list_counties()
```

---

## 環境需求

- Python >= 3.10
- CWA Open Data API Key（[申請連結](https://opendata.cwa.gov.tw/user/apply/2)）

## 環境變數

| 變數 | 必填 | 預設值 | 說明 |
|------|:----:|--------|------|
| `CWA_API_KEY` | ✓ | — | 中央氣象署 API 授權碼 |
| `HTTP_HOST` | | `0.0.0.0` | HTTP 模式綁定位址 |
| `HTTP_PORT` | | `8000` | HTTP 模式端口 |
| `CACHE_TTL_HOURS` | | `24` | 快取有效期（小時）|
| `CORS_ALLOWED_ORIGINS` | | `localhost:3000,8000`（dev）| CORS 允許來源，逗號分隔 |
| `MCP_ENABLE_DNS_PROTECTION` | | `false` | 啟用 DNS rebinding 保護；Docker 內網建議設為 `false` |

---

## 安裝與啟動

### 本機開發

```bash
# 1. 複製設定檔
cp .env.example .env
# 編輯 .env，填入 CWA_API_KEY

# 2. 建立虛擬環境並安裝
python3 -m venv .venv
.venv/bin/pip install .

# 3a. STDIO 模式
PYTHONPATH=src .venv/bin/python src/main.py

# 3b. HTTP 模式（Streamable HTTP）
PYTHONPATH=src .venv/bin/python src/main.py --http --port 8000
```

### Docker（獨立啟動）

```bash
# 複製設定檔
cp .env.example .env
# 編輯 .env，填入 CWA_API_KEY

# HTTP 模式（Streamable HTTP，供 Open WebUI 原生 MCP 連線使用）
docker-compose up mcp-weather-http

# STDIO 模式
docker-compose up mcp-weather
```

### Docker（整合 open-webui）

在 open-webui 的 `docker-compose.yaml` 加入以下 service：

```yaml
mcp-weather-http:
  build:
    context: /path/to/mcp-taiwan-weather
    target: production
  container_name: mcp-weather-http
  ports:
    - "8101:8001"
  env_file:
    - .env                        # CWA_API_KEY 從此讀取
  environment:
    - PYTHONPATH=/app/src
    - PYTHONUNBUFFERED=1
    - HTTP_HOST=0.0.0.0
    - HTTP_PORT=8001
  command: ["python", "-m", "http_server"]
  restart: unless-stopped
  networks:
    - ollama-network
  extra_hosts:
    - "host.docker.internal:host-gateway"
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 20s
```

Open WebUI 新增一條原生 MCP 連線（Admin → Settings → Tools）：

| 欄位 | 值 |
|---|---|
| type | `mcp` |
| id | `mcp-weather` |
| url | `http://mcp-weather-http:8001/mcp/` |

再把 `server:mcp:mcp-weather` 加進要使用的模型的 `info.meta.toolIds`。

> 📜 舊版這裡是改 `mcpo-config.json`。**MCPO 已於 2026-08-11 除役**，
> 該檔案已無作用。本模組也不再提供 `/sse/` 端點。

---

## 整合設定

### Claude Desktop（STDIO 模式）

編輯 `~/Library/Application Support/Claude/claude_desktop_config.json`：

**本機 Python**

```json
{
  "mcpServers": {
    "mcp-weather": {
      "command": "/path/to/mcp-taiwan-weather/.venv/bin/python",
      "args": ["/path/to/mcp-taiwan-weather/src/main.py"],
      "env": {
        "PYTHONPATH": "/path/to/mcp-taiwan-weather/src",
        "CWA_API_KEY": "CWA-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
      }
    }
  }
}
```

**Docker 容器（exec 進執行中容器）**

```json
{
  "mcpServers": {
    "mcp-weather": {
      "command": "docker",
      "args": [
        "exec", "-i", "mcp-weather-dev",
        "python", "-m", "server"
      ]
    }
  }
}
```

> `mcp-weather-dev` 為容器名稱，需先確認容器已啟動：`docker-compose up mcp-weather`

### Open WebUI（本機 HTTP 模式）

先啟動 HTTP server，再到 Open WebUI 新增原生 MCP 連線指向它：

```bash
PYTHONPATH=src CWA_API_KEY=xxx .venv/bin/python src/main.py --http --port 8000
```

```json
{
  "mcp-weather": {
    "type": "streamable-http",
    "url": "http://localhost:8000/mcp/"
  }
}
```

---

## API 端點（HTTP 模式）

| 端點 | 用途 | 說明 |
|------|------|------|
| `GET /` | 人 | 伺服器資訊與端點列表 |
| `GET /health` | Docker | Healthcheck，回傳 `{"status":"ok"}` |
| `GET /docs` | 人 | Swagger UI |
| `GET /openapi.json` | 人 | OpenAPI 規格 |
| `POST /mcp/` | Open WebUI / MCP 客戶端 | MCP over Streamable HTTP（由 ASGI mount 處理） |

> `/mcp/*` 完全由 MCP SDK 的 `StreamableHTTPSessionManager` ASGI app 接管
> （`app.mount("/mcp", mcp_server.create_asgi_app())`），FastAPI 不介入。
> 其餘端點為人工管理與 Docker healthcheck 用途。
>
> 以 `stateless=True` + `json_response=True` 執行：回應是 `application/json`，
> 不是 `text/event-stream`；沒有伺服器端 session，因此前面**不需要 sticky routing**。
>
> **2026-07-28 世代的請求要求**（SEP-2243）：必須帶 `Mcp-Method` header
> （呼叫工具時另帶 `Mcp-Name`），且 `params._meta` 需含
> `io.modelcontextprotocol/protocolVersion`、`/clientInfo`、`/clientCapabilities`。
> 缺信封回 `400 / -32602`；header 與 body 的 method 不一致回 `400 / -32020`。
> handshake 世代（Open WebUI 原生連線走這條）維持原本的 `initialize` 流程，不受影響。
>
> 舊的 `GET /sse/` 與 `POST /sse/messages` **已移除**，現在回 404。

---

## 專案結構

```
mcp-taiwan-weather/
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── constraints.txt          # 相依版本鎖定（pip install -c）
├── src/
│   ├── main.py              # 統一入口（--http flag 切換模式）
│   ├── server.py            # STDIO 獨立入口
│   ├── http_server.py       # HTTP 獨立入口（委派給 main.run_http_mode）
│   ├── protocol/
│   │   ├── base_server.py       # Transport-agnostic MCP 核心
│   │   ├── stdio_server.py      # STDIO transport
│   │   └── streamable_server.py # Streamable HTTP transport
│   ├── core/
│   │   └── config.py        # 環境變數設定
│   ├── weather/
│   │   ├── cache.py         # TTL 快取（24 小時）
│   │   ├── cwa_client.py    # CWA API 呼叫 + 回應格式化
│   │   └── dataset_mapping.py  # 縣市 → Dataset ID 對應
│   └── tools/
│       └── definitions.py   # MCP Tool 定義與 handler
└── tests/
    └── integration/
        └── test_mcp_protocol.py  # 協議層測試（含兩世代相容性）
```

CORS 由 `main.py` 的 `CORSMiddleware` 統一處理，`allow_headers` 已放行
`Mcp-Method` / `Mcp-Name` / `MCP-Protocol-Version` / `Mcp-Session-Id`
（舊版由 `sse_server.py` 自行手寫注入 header，該檔已移除）。

## 測試

```bash
pytest tests -q
```

`tests/integration/test_mcp_protocol.py` 涵蓋工具定義契約、handler 契約，
以及**同一 `/mcp/` 端點對兩個協議世代都要能服務**的相容性 —— 改動 transport
或升級 MCP SDK 後必跑。

## 資料來源

- API：[中央氣象署開放資料平台](https://opendata.cwa.gov.tw/)
- 資料集：F-D0047 系列（臺灣各縣市鄉鎮未來 1 週逐 12 小時天氣預報）
- 更新頻率：每 6 小時（05:30、11:30、17:30、23:30 台灣時間）
