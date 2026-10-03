from __future__ import annotations

import json
import os
import sys
from contextlib import AsyncExitStack
from typing import Any, Protocol

from commerce_support_demo.service.commerce import CommerceError, CommerceService
from commerce_support_demo.settings import Settings


class CommerceGateway(Protocol):
    async def call(self, tool_name: str, **arguments: Any) -> dict[str, Any]: ...

    async def close(self) -> None: ...


class InProcessCommerceGateway:
    def __init__(self, service: CommerceService) -> None:
        self._service = service

    async def call(self, tool_name: str, **arguments: Any) -> dict[str, Any]:
        handler = getattr(self._service, tool_name, None)
        if handler is None:
            raise CommerceError(
                "unsupported_tool", "The requested Demo tool is not available.", 500
            )
        return handler(**arguments)

    async def close(self) -> None:
        return None


class MCPCommerceGateway:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._stack = AsyncExitStack()
        self._session: Any = None

    async def start(self) -> None:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        environment: dict[str, str] = {}
        for name in ("PATH", "PYTHONPATH", "LANG", "LC_ALL"):
            value = os.getenv(name)
            if value is not None:
                environment[name] = value
        environment["DEMO_MCP_SIGNING_KEY"] = self._settings.mcp_signing_key
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "commerce_support_demo.mcp.server"],
            env=environment,
        )
        read, write = await self._stack.enter_async_context(stdio_client(params))
        self._session = await self._stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()

    async def call(self, tool_name: str, **arguments: Any) -> dict[str, Any]:
        if self._session is None:
            raise CommerceError("mcp_unavailable", "The local Demo MCP service is not ready.", 503)
        try:
            result = await self._session.call_tool(tool_name, arguments)
        except Exception as error:
            raise CommerceError(
                "mcp_unavailable", "The local Demo MCP service failed.", 503
            ) from error
        if getattr(result, "isError", False):
            raise CommerceError("mcp_tool_error", "The local Demo MCP tool returned an error.", 502)
        content = getattr(result, "content", [])
        if not content or not getattr(content[0], "text", None):
            raise CommerceError(
                "mcp_invalid_response", "The local Demo MCP tool returned no structured data.", 502
            )
        try:
            payload = json.loads(content[0].text)
        except json.JSONDecodeError as error:
            raise CommerceError(
                "mcp_invalid_response", "The local Demo MCP response was not JSON.", 502
            ) from error
        if not isinstance(payload, dict) or "schema_version" not in payload:
            raise CommerceError(
                "mcp_invalid_response", "The local Demo MCP response violated its contract.", 502
            )
        return payload

    async def close(self) -> None:
        await self._stack.aclose()
