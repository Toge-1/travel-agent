from __future__ import annotations

from typing import Any
from mcp.server.fastmcp import FastMCP
from app.config import get_settings
from app.amap_client import AMapClient


settings = get_settings()
client = AMapClient(settings.amap_api_key)

mcp = FastMCP("amap-tools")


@mcp.tool()
async def amap_search_poi(
    city: str,
    keywords: str,
    types: str | None = None,
    max_results: int = 10,
) -> dict[str, Any]:
    """Search POI by keywords in a city."""
    raw = await client.search_poi(
        keywords=keywords,
        city=city,
        types=types,
        offset=max_results,
        page=1,
    )
    pois = raw.get("pois", [])
    return {
        "count": raw.get("count"),
        "pois": [
            {
                "name": p.get("name"),
                "location": p.get("location"),
                "address": p.get("address"),
                "type": p.get("type"),
                "tel": p.get("tel"),
            }
            for p in pois
        ],
        "raw": raw,
    }


@mcp.tool()
async def amap_weather(city: str) -> dict[str, Any]:
    """Get current weather info for a city."""
    raw = await client.weather(city=city, extensions="base")
    lives = raw.get("lives", [])
    first = lives[0] if lives else {}
    return {
        "weather": {
            "city": first.get("city"),
            "weather": first.get("weather"),
            "temperature": first.get("temperature"),
            "report_time": first.get("reporttime"),
        },
        "raw": raw,
    }


@mcp.tool()
async def amap_route(origin_city: str, destination_city: str) -> dict[str, Any]:
    """Get driving route summary between two cities."""
    geocode_origin = await client.geocode(origin_city)
    geocode_dest = await client.geocode(destination_city)

    origin_list = geocode_origin.get("geocodes", [])
    dest_list = geocode_dest.get("geocodes", [])

    if not origin_list or not dest_list:
        return {"error": "geocode_failed", "raw": {"origin": geocode_origin, "dest": geocode_dest}}

    origin_loc = origin_list[0].get("location")
    dest_loc = dest_list[0].get("location")

    raw = await client.driving_route(origin=origin_loc, destination=dest_loc)
    route = raw.get("route", {})
    paths = route.get("paths", [])
    first = paths[0] if paths else {}
    return {
        "route": {
            "distance": first.get("distance"),
            "duration": first.get("duration"),
            "taxi_cost": first.get("taxi_cost"),
        },
        "raw": raw,
    }


if __name__ == "__main__":
    mcp.run()
