from __future__ import annotations

from typing import Any
from dataclasses import dataclass
import asyncio
import json
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model


@dataclass
class MCPToolSpec:
    name: str
    description: str | None
    input_schema: dict[str, Any]


class MCPToolRegistry:
    def __init__(self, command: str, args: list[str]) -> None:
        self.command = command
        self.args = args
        self._client_cm = None
        self._session: ClientSession | None = None
        self._tools: list[MCPToolSpec] = []
        self._lock = asyncio.Lock()

    async def startup(self) -> None:
        # Ensure MCP subprocess inherits current environment variables.
        params = StdioServerParameters(command=self.command, args=self.args, env=dict(os.environ))
        self._client_cm = stdio_client(params)
        read, write = await self._client_cm.__aenter__()
        self._session = ClientSession(read, write)
        await self._session.__aenter__()
        await self._session.initialize()
        tools = await self._session.list_tools()
        self._tools = [
            MCPToolSpec(name=t.name, description=t.description, input_schema=t.inputSchema)
            for t in tools.tools
        ]

    async def shutdown(self) -> None:
        if self._session is not None:
            await self._session.__aexit__(None, None, None)
        if self._client_cm is not None:
            await self._client_cm.__aexit__(None, None, None)

    def list_tools(self) -> list[MCPToolSpec]:
        return list(self._tools)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if self._session is None:
            raise RuntimeError("MCP session not initialized")
        async with self._lock:
            result = await self._session.call_tool(name, arguments)
        if result.isError:
            return {"error": True, "content": result.content}

        text_parts: list[str] = []
        json_parts: list[Any] = []
        for item in result.content:
            if hasattr(item, "text"):
                text_parts.append(item.text)
                try:
                    json_parts.append(json.loads(item.text))
                except json.JSONDecodeError:
                    pass

        return {
            "error": False,
            "content": text_parts,
            "json": json_parts,
            "raw": result,
        }

    def as_langchain_tools(self) -> list[StructuredTool]:
        tools: list[StructuredTool] = []
        for spec in self._tools:
            args_schema = build_pydantic_from_schema(spec.input_schema)

            async def _runner(_spec: MCPToolSpec = spec, **kwargs: Any) -> dict[str, Any]:
                return await self.call_tool(_spec.name, kwargs)

            tool = StructuredTool.from_function(
                func=_runner,
                name=spec.name,
                description=spec.description or "",
                args_schema=args_schema,
                coroutine=_runner,
            )
            tools.append(tool)
        return tools


def build_pydantic_from_schema(schema: dict[str, Any]) -> type[BaseModel]:
    properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
    required = set(schema.get("required", [])) if isinstance(schema, dict) else set()
    fields: dict[str, tuple[Any, Any]] = {}

    for name, prop in properties.items():
        ptype = prop.get("type", "string")
        default = ... if name in required else None
        annotation = _json_type_to_py(ptype, prop)
        fields[name] = (annotation, Field(default=default))

    return create_model("MCPArgs", **fields)  # type: ignore[arg-type]


def _json_type_to_py(ptype: str, prop: dict[str, Any]) -> Any:
    if ptype == "string":
        return str
    if ptype == "number":
        return float
    if ptype == "integer":
        return int
    if ptype == "boolean":
        return bool
    if ptype == "array":
        items = prop.get("items", {})
        return list[_json_type_to_py(items.get("type", "string"), items)]
    if ptype == "object":
        return dict[str, Any]
    return Any
