"""MCP Streamable HTTP client helpers for the backend."""

from __future__ import annotations

import json
import os
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

MCP_URL = os.environ.get("MCP_URL", "http://localhost:8101/mcp")


def _text_content(result: Any) -> str:
    parts: list[str] = []
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts) if parts else json.dumps({"error": "empty tool result"})


async def call_tool(name: str, arguments: dict[str, Any] | None = None) -> str:
    async with streamablehttp_client(MCP_URL) as (read, write, _get_session_id):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name, arguments or {})
            return _text_content(result)


async def list_tool_names() -> list[str]:
    async with streamablehttp_client(MCP_URL) as (read, write, _get_session_id):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            return [t.name for t in listed.tools]
