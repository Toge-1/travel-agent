# LangGraph 多智能体旅行规划器

基于 LangGraph 的多智能体工作流，集成高德 Web 服务 API，并提供 FastAPI REST 服务。MCP 用作工具注册中心，智能体在运行时动态绑定工具。

## 功能
- 城市到城市的行程规划：POI 搜索、天气、酒店选择、路线摘要
- 角色化智能体：`attraction_node`、`weather_node`、`hotel_node`、`route_node`、`planner_node`
- 启动时 MCP 动态绑定工具
- REST 接口：`/plan`、`/tools`、`/health`
- 内置前端页面（`http://127.0.0.1:8000`）

## 环境要求
- Python 3.10+
- OpenAI API Key
- 高德 Web 服务 API Key

## 安装
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## 配置
复制 `.env.example` 为 `.env`，并填写：
- `OPENAI_API_KEY`
- `AMAP_API_KEY`

`OPENAI_BASE_URL` 和 `OPENAI_MODEL` 已在代码中默认设置为：
- `https://dashscope.aliyuncs.com/compatible-mode/v1`
- `qwen-plus`

如果需要覆盖，仍可在 `.env` 中显式设置。

## 运行
```bash
cd C:\Users\34781\travel-agent
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## 请求示例
```bash
curl -X POST "http://127.0.0.1:8000/plan" \
  -H "Content-Type: application/json" \
  -d '{
    "origin_city": "Shanghai",
    "destination_city": "Hangzhou",
    "start_date": "2026-03-05",
    "days": 3,
    "travelers": 2,
    "budget_level": "moderate",
    "hotel_level": "comfort",
    "preferences": ["museum", "food", "night view"],
    "pace": "balanced"
  }'
```

## MCP 工具
服务通过 stdio 启动 `app.mcp_server` 并动态加载工具：
- `amap_search_poi`
- `amap_weather`
- `amap_route`

可通过 `/tools` 查看工具 schema。

## 项目结构
```
travel-agent/
  app/
    amap_client.py
    config.py
    main.py
    mcp_registry.py
    mcp_server.py
    schemas.py
    workflow.py
    static/
      index.html
      styles.css
      app.js
  .env.example
  requirements.txt
  README.md
```

## 高德文档
创建 Key 与 Web 服务 API 官方文档：
```
https://lbs.amap.com/api/webservice/guide/create-project/get-key
https://lbs.amap.com/api/webservice/guide/api/weatherinfo
https://lbs.amap.com/api/webservice/guide/api/search
https://lbs.amap.com/api/webservice/guide/api/direction
```
