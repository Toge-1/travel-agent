from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, TypedDict
from datetime import timedelta

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END

from app.schemas import TripRequest
from app.mcp_registry import MCPToolRegistry


logger = logging.getLogger("travel-agent")


class TripState(TypedDict):
    request: TripRequest
    attractions: list[dict[str, Any]]
    hotels: list[dict[str, Any]]
    weather: dict[str, Any]
    route: dict[str, Any]
    plan: dict[str, Any]


async def _call_with_retries(
    label: str,
    timeout_sec: int,
    max_retries: int,
    backoff_sec: float,
    func,
):
    attempt = 0
    while True:
        try:
            start = time.monotonic()
            result = await asyncio.wait_for(func(), timeout=timeout_sec)
            elapsed = time.monotonic() - start
            logger.info("%s ok in %.2fs", label, elapsed)
            if elapsed > timeout_sec * 0.8:
                logger.warning("%s slow: %.2fs (timeout=%ss)", label, elapsed, timeout_sec)
            return result
        except Exception as exc:  # noqa: BLE001
            if attempt >= max_retries:
                logger.exception("%s failed after %s attempts", label, attempt + 1)
                raise
            logger.warning("%s failed (attempt %s/%s): %s", label, attempt + 1, max_retries + 1, exc)
            await asyncio.sleep(backoff_sec * (2 ** attempt))
            attempt += 1


def create_graph(
    registry: MCPToolRegistry,
    openai_api_key: str,
    openai_base_url: str | None,
    model: str,
    llm_timeout_sec: int,
    tool_timeout_sec: int,
    llm_max_retries: int,
    tool_max_retries: int,
    retry_backoff_sec: float,
):
    tools = registry.as_langchain_tools()
    tool_map = {t.name: t for t in tools}

    llm = ChatOpenAI(
        api_key=openai_api_key,
        base_url=openai_base_url,
        model=model,
        temperature=0.4,
    )

    async def _call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
        tool = tool_map.get(name)
        if tool is None:
            raise RuntimeError(f"tool not found: {name}")
        return await _call_with_retries(
            f"tool:{name}",
            tool_timeout_sec,
            tool_max_retries,
            retry_backoff_sec,
            lambda: tool.ainvoke(args),
        )

    async def attraction_node(state: TripState) -> TripState:
        req = state["request"]
        logger.info("node:attraction start city=%s", req.destination_city)
        prefs = ", ".join(req.preferences) if req.preferences else "地标, 文化, 美食"
        result = await _call_tool(
            "amap_search_poi",
            {"city": req.destination_city, "keywords": prefs, "max_results": 10},
        )
        poi_list = _extract_pois([result])
        logger.info("node:attraction done count=%s", len(poi_list))
        return {**state, "attractions": poi_list}

    async def weather_node(state: TripState) -> TripState:
        req = state["request"]
        logger.info("node:weather start city=%s", req.destination_city)
        result = await _call_tool("amap_weather", {"city": req.destination_city})
        weather = _extract_weather([result])
        logger.info("node:weather done has_weather=%s", bool(weather))
        return {**state, "weather": weather}

    async def hotel_node(state: TripState) -> TripState:
        req = state["request"]
        hotel_level = req.hotel_level or "comfort"
        logger.info("node:hotel start city=%s level=%s", req.destination_city, hotel_level)
        result = await _call_tool(
            "amap_search_poi",
            {"city": req.destination_city, "keywords": f"{hotel_level} hotel", "types": "hotel", "max_results": 10},
        )
        hotels = _extract_pois([result])
        logger.info("node:hotel done count=%s", len(hotels))
        return {**state, "hotels": hotels}

    async def route_node(state: TripState) -> TripState:
        req = state["request"]
        logger.info("node:route start %s->%s", req.origin_city, req.destination_city)
        result = await _call_tool(
            "amap_route",
            {"origin_city": req.origin_city, "destination_city": req.destination_city},
        )
        route = _extract_route([result])
        logger.info("node:route done has_route=%s", bool(route))
        return {**state, "route": route}

    async def planner_node(state: TripState) -> TripState:
        req = state["request"]
        days = req.days
        start_date = req.start_date
        attractions = state.get("attractions", [])
        hotels = state.get("hotels", [])
        weather = state.get("weather", {})
        route = state.get("route", {})

        logger.info("node:planner start days=%s", days)
        system_prompt = (
            "你是专业行程规划师。请输出中文行程，格式必须是 JSON。"
            "JSON 结构：{\"overview\": string, \"days\": [{\"title\": string, \"schedule\": [string]}]}。"
            "schedule 每项必须是字符串，不要输出对象。"
        )

        day_labels = [str(start_date + timedelta(days=i)) for i in range(days)]
        user_prompt = (
            f"目的地：{req.destination_city}\n"
            f"日期：{day_labels}\n"
            f"节奏：{req.pace}\n"
            f"偏好：{req.preferences}\n"
            f"景点候选：{attractions}\n"
            f"酒店候选：{hotels}\n"
            f"天气：{weather}\n"
            f"路线：{route}\n"
            "每天安排 3-5 个活动，中文输出。"
        )

        ai = await _call_with_retries(
            "planner_llm",
            llm_timeout_sec,
            llm_max_retries,
            retry_backoff_sec,
            lambda: llm.ainvoke([SystemMessage(system_prompt), HumanMessage(user_prompt)]),
        )
        plan = _safe_json(ai.content)
        logger.info("node:planner done has_days=%s", len(plan.get("days", [])) if isinstance(plan, dict) else 0)
        return {**state, "plan": plan}

    graph = StateGraph(TripState)
    graph.add_node("attraction_node", attraction_node)
    graph.add_node("weather_node", weather_node)
    graph.add_node("hotel_node", hotel_node)
    graph.add_node("route_node", route_node)
    graph.add_node("planner_node", planner_node)

    graph.set_entry_point("attraction_node")
    graph.add_edge("attraction_node", "weather_node")
    graph.add_edge("weather_node", "hotel_node")
    graph.add_edge("hotel_node", "route_node")
    graph.add_edge("route_node", "planner_node")
    graph.add_edge("planner_node", END)

    return graph.compile()


def _safe_json(content: str | None) -> dict[str, Any]:
    import json

    if not content:
        return {"overview": "", "days": []}

    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        content = content.replace("json", "", 1).strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"overview": content, "days": []}


def _extract_pois(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for result in results:
        for item in result.get("json", []):
            if isinstance(item, dict) and "pois" in item:
                return item.get("pois", [])
    return []


def _extract_weather(results: list[dict[str, Any]]) -> dict[str, Any]:
    for result in results:
        for item in result.get("json", []):
            if isinstance(item, dict) and "weather" in item:
                return item.get("weather", {})
    return {}


def _extract_route(results: list[dict[str, Any]]) -> dict[str, Any]:
    for result in results:
        for item in result.get("json", []):
            if isinstance(item, dict) and "route" in item:
                return item.get("route", {})
    return {}
