from __future__ import annotations

import logging
import asyncio
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.mcp_registry import MCPToolRegistry
from app.schemas import TripRequest, TripResponse, TripPlan, POIItem, WeatherInfo, RouteInfo, DayPlan
from app.workflow import create_graph, TripState


app = FastAPI(title="LangGraph Travel Agent", version="0.1.0")
logging.basicConfig(level=logging.INFO)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _normalize_schedule(items: Any) -> list[str]:
    if not items:
        return []
    normalized: list[str] = []
    if isinstance(items, list):
        for item in items:
            if isinstance(item, str):
                normalized.append(item)
            elif isinstance(item, dict):
                time = item.get("time") or item.get("when") or ""
                activity = item.get("activity") or item.get("title") or item.get("desc") or item.get("description") or ""
                if time and activity:
                    normalized.append(f"{time} {activity}")
                elif activity:
                    normalized.append(str(activity))
                else:
                    normalized.append(str(item))
            else:
                normalized.append(str(item))
    else:
        normalized.append(str(items))
    return normalized


def _normalize_poi(p: dict[str, Any]) -> dict[str, Any]:
    tel = p.get("tel")
    if isinstance(tel, list):
        p["tel"] = ", ".join(str(x) for x in tel if x)
    elif tel is None:
        p["tel"] = None
    else:
        p["tel"] = str(tel)
    return p


@app.on_event("startup")
async def on_startup() -> None:
    settings = get_settings()
    registry = MCPToolRegistry(settings.mcp_server_command, settings.mcp_server_args)
    await registry.startup()

    graph = create_graph(
        registry=registry,
        openai_api_key=settings.openai_api_key,
        openai_base_url=settings.openai_base_url,
        model=settings.openai_model,
        llm_timeout_sec=settings.llm_timeout_sec,
        tool_timeout_sec=settings.tool_timeout_sec,
        llm_max_retries=settings.llm_max_retries,
        tool_max_retries=settings.tool_max_retries,
        retry_backoff_sec=settings.retry_backoff_sec,
    )

    app.state.settings = settings
    app.state.registry = registry
    app.state.graph = graph


@app.on_event("shutdown")
async def on_shutdown() -> None:
    registry: MCPToolRegistry | None = getattr(app.state, "registry", None)
    if registry is not None:
        await registry.shutdown()


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/tools")
async def tools() -> dict:
    registry: MCPToolRegistry = app.state.registry
    return {
        "tools": [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in registry.list_tools()
        ]
    }


@app.post("/plan", response_model=TripResponse)
async def plan_trip(request: TripRequest) -> TripResponse:
    graph = app.state.graph

    initial: TripState = {
        "request": request,
        "attractions": [],
        "hotels": [],
        "weather": {},
        "route": {},
        "plan": {},
    }

    settings = app.state.settings
    try:
        result = await asyncio.wait_for(graph.ainvoke(initial), timeout=settings.plan_timeout_sec)
    except asyncio.TimeoutError:
        return JSONResponse(status_code=504, content={"error": "plan_timeout", "detail": "Exceeded plan timeout"})

    plan = result.get("plan", {})
    days = []
    for i, day in enumerate(plan.get("days", []), start=1):
        schedule = _normalize_schedule(day.get("schedule", [])) if isinstance(day, dict) else []
        days.append(DayPlan(day_index=i, title=day.get("title", "") if isinstance(day, dict) else "", schedule=schedule))

    raw_payload = dict(result)
    raw_payload["request"] = request.model_dump()

    response = TripResponse(
        request=request,
        plan=TripPlan(
            overview=plan.get("overview", ""),
            days=days,
            attractions=[POIItem(**_normalize_poi(p)) for p in result.get("attractions", [])],
            hotels=[POIItem(**_normalize_poi(p)) for p in result.get("hotels", [])],
            weather=WeatherInfo(**result.get("weather", {})) if result.get("weather") else None,
            route=RouteInfo(**result.get("route", {})) if result.get("route") else None,
        ),
        raw=raw_payload,
    )

    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": str(exc)})
