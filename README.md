# mcp-taiwan-weather

台灣一週天氣預報 MCP Server，資料來源為[中央氣象署開放資料平台](https://opendata.cwa.gov.tw/)。

支援兩種運行模式：
- **STDIO 模式** — 直接整合 Claude Desktop
- **HTTP/SSE 模式** — 透過 [MCPO](https://github.com/open-webui/mcpo) proxy 整合

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

# 3b. HTTP/SSE 模式
PYTHONPATH=src .venv/bin/python src/main.py --http --port 8000
```

### Docker（獨立啟動）

```bash
# 複製設定檔
cp .env.example .env
# 編輯 .env，填入 CWA_API_KEY

# HTTP/SSE 模式（供 MCPO 使用）
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

MCPO config（`mcpo-config.json`）加入：

```json
{
  "mcpServers": {
    "mcp-weather": {
      "url": "http://mcp-weather-http:8001/sse/"
    }
  }
}
```

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

### MCPO（本機 HTTP/SSE 模式）

先啟動 HTTP server，再設定 MCPO：

```bash
PYTHONPATH=src CWA_API_KEY=xxx .venv/bin/python src/main.py --http --port 8000
```

```json
{
  "mcp-weather": {
    "url": "http://localhost:8000/sse/"
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
| `GET /sse/` | MCPO | MCP SSE 連線建立 |
| `POST /sse/messages` | MCPO | MCP 訊息接收 |

> MCPO 只使用 `/sse/` 與 `/sse/messages`，其餘端點為人工管理與 Docker healthcheck 用途。

---

## 專案結構

```
mcp-taiwan-weather/
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── src/
    ├── main.py              # 統一入口（--http flag 切換模式）
    ├── server.py            # STDIO 獨立入口
    ├── http_server.py       # HTTP 獨立入口
    ├── protocol/
    │   ├── base_server.py   # Transport-agnostic MCP 核心
    │   ├── stdio_server.py  # STDIO transport
    │   └── sse_server.py    # SSE/HTTP transport + CORS
    ├── core/
    │   └── config.py        # 環境變數設定
    ├── weather/
    │   ├── cache.py         # TTL 快取（24 小時）
    │   ├── cwa_client.py    # CWA API 呼叫 + 回應格式化
    │   └── dataset_mapping.py  # 縣市 → Dataset ID 對應
    └── tools/
        └── definitions.py   # MCP Tool 定義與 handler
```

## 資料來源

- API：[中央氣象署開放資料平台](https://opendata.cwa.gov.tw/)
- 資料集：F-D0047 系列（臺灣各縣市鄉鎮未來 1 週逐 12 小時天氣預報）
- 更新頻率：每 6 小時（05:30、11:30、17:30、23:30 台灣時間）
