from __future__ import annotations

from typing import Any
import httpx


class AMapClient:
    def __init__(self, api_key: str, timeout: float = 10.0) -> None:
        self.api_key = api_key
        self._client = httpx.AsyncClient(timeout=timeout, base_url="https://restapi.amap.com")

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        params = {**params, "key": self.api_key}
        resp = await self._client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    async def geocode(self, address: str, city: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"address": address}
        if city:
            params["city"] = city
        return await self._get("/v3/geocode/geo", params)

    async def search_poi(
        self,
        keywords: str,
        city: str,
        types: str | None = None,
        offset: int = 10,
        page: int = 1,
        extensions: str = "all",
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "keywords": keywords,
            "city": city,
            "offset": offset,
            "page": page,
            "extensions": extensions,
        }
        if types:
            params["types"] = types
        return await self._get("/v3/place/text", params)

    async def weather(self, city: str, extensions: str = "base") -> dict[str, Any]:
        params = {"city": city, "extensions": extensions}
        return await self._get("/v3/weather/weatherInfo", params)

    async def driving_route(self, origin: str, destination: str) -> dict[str, Any]:
        params = {"origin": origin, "destination": destination}
        return await self._get("/v3/direction/driving", params)
