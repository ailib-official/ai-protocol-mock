"""MCP JSON-RPC Mock - tools/list, tools/call, capabilities.

MCP JSON-RPC 模拟模块：实现 tools/list、tools/call、capabilities、initialize。
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from ai_protocol_mock import __version__

# Default tools for mock
DEFAULT_TOOLS = [
    {
        "name": "read_file",
        "description": "Read a file from disk",
        "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    },
    {
        "name": "search",
        "description": "Search the web",
        "inputSchema": {"type": "object"},
    },
]


def create_mcp_router() -> APIRouter:
    """Create MCP JSON-RPC 2.0 mock router."""
    router = APIRouter()

    @router.post("/mcp")
    async def mcp_json_rpc(request: Request):
        """Handle JSON-RPC 2.0 requests."""
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                status_code=200,
                content={
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error"},
                },
            )
        if not isinstance(body, dict):
            req_id = None
            return JSONResponse(
                status_code=200,
                content={
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32600, "message": "Invalid Request"},
                },
            )
        method = body.get("method")
        req_id = body.get("id")
        params = body.get("params") or {}

        if method == "tools/list":
            result = {"tools": DEFAULT_TOOLS}
            return JSONResponse(content={"jsonrpc": "2.0", "id": req_id, "result": result})
        if method == "tools/call":
            tool_name = params.get("name", "read_file")
            tool_args = params.get("arguments", {})
            # Support streaming if requested
            stream = params.get("stream", False)
            if stream:

                def gen():
                    content = f"Mock result for {tool_name} with args {tool_args}"
                    yield f"data: {json.dumps({'content': [{'type': 'text', 'text': content}]})}\n\n"
                    yield "data: [DONE]\n\n"

                return StreamingResponse(gen(), media_type="text/event-stream")
            result = {
                "content": [{"type": "text", "text": f"Mock result for {tool_name} with args {tool_args}"}],
                "isError": False,
            }
            return JSONResponse(content={"jsonrpc": "2.0", "id": req_id, "result": result})
        if method == "capabilities":
            result = {
                "capabilities": {
                    "tools": {"listChanged": False},
                },
            }
            return JSONResponse(content={"jsonrpc": "2.0", "id": req_id, "result": result})
        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "ai-protocol-mock", "version": __version__},
            }
            return JSONResponse(content={"jsonrpc": "2.0", "id": req_id, "result": result})

        return JSONResponse(
            status_code=200,
            content={
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            },
        )

    return router
