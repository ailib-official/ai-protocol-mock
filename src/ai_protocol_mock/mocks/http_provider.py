"""HTTP Provider Mock - manifest-driven, supports OpenAI and non-OpenAI formats."""

from __future__ import annotations

import asyncio
import random
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from ai_protocol_mock.config import config


def _load_manifests(manifest_dir: Path) -> dict[str, dict[str, Any]]:
    """Load all provider manifests from directory."""
    manifests: dict[str, dict[str, Any]] = {}
    providers_dir = manifest_dir / "v1" / "providers"
    if not providers_dir.exists():
        providers_dir = manifest_dir / "providers"
    if not providers_dir.exists():
        return manifests

    for f in providers_dir.glob("*.yaml"):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            if data and isinstance(data, dict):
                pid = data.get("id", f.stem)
                manifests[pid] = data
        except Exception:
            pass
    return manifests


def _detect_api_style(manifest: dict[str, Any]) -> str:
    """Detect API style from manifest. Returns 'openai' or 'anthropic'."""
    endpoint = manifest.get("endpoint") or manifest.get("endpoints") or {}
    if isinstance(endpoint, dict):
        chat = endpoint.get("chat", "")
    else:
        chat = ""
    # Anthropic uses /messages, OpenAI uses /chat/completions
    if "/messages" in chat or "messages" in chat:
        return "anthropic"
    return "openai"


def _openai_response(content: str, model: str, stream: bool, usage: dict | None = None) -> dict | list[dict]:
    """Generate OpenAI-format response."""
    if stream:
        chunks = []
        for i, char in enumerate(content):
            chunks.append({
                "id": "chatcmpl-mock",
                "object": "chat.completion.chunk",
                "created": 1699012345,
                "model": model,
                "choices": [{"index": 0, "delta": {"content": char}, "finish_reason": None}],
            })
        chunks.append({
            "id": "chatcmpl-mock",
            "object": "chat.completion.chunk",
            "created": 1699012345,
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        })
        return chunks
    resp = {
        "id": "chatcmpl-mock",
        "object": "chat.completion",
        "created": 1699012345,
        "model": model,
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
        ],
    }
    if usage:
        resp["usage"] = usage
    else:
        resp["usage"] = {"prompt_tokens": 10, "completion_tokens": len(content.split()), "total_tokens": 10 + len(content.split())}
    return resp


def _anthropic_response(content: str, model: str, stream: bool, usage: dict | None = None) -> dict | list[dict]:
    """Generate Anthropic-format response."""
    if stream:
        chunks = [
            {
                "type": "message_start",
                "message": {
                    "id": "msg-mock",
                    "type": "message",
                    "role": "assistant",
                    "content": [],
                    "model": model,
                    "stop_reason": None,
                    "usage": {"input_tokens": 10, "output_tokens": 0},
                },
            },
            {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        ]
        for char in content:
            chunks.append({"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": char}})
        chunks.extend([
            {"type": "content_block_stop", "index": 0},
            {"type": "message_stop"},
        ])
        return chunks
    resp = {
        "id": "msg-mock",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [{"type": "text", "text": content}],
        "stop_reason": "end_turn",
    }
    if usage:
        resp["usage"] = usage
    else:
        resp["usage"] = {"input_tokens": 10, "output_tokens": len(content.split())}
    return resp


def create_http_router(manifest_dir: Path | None = None) -> APIRouter:
    """Create FastAPI router with manifest-driven HTTP mock routes."""
    router = APIRouter()
    mdir = manifest_dir or config.MANIFEST_DIR
    manifests = _load_manifests(mdir)

    # Build route map: path -> (provider_id, api_style)
    route_map: dict[str, tuple[str, str]] = {}
    for pid, m in manifests.items():
        style = _detect_api_style(m)
        ep = m.get("endpoint") or m.get("endpoints") or {}
        chat_path = ep.get("chat", "/chat/completions") if isinstance(ep, dict) else "/chat/completions"
        if not chat_path.startswith("/"):
            chat_path = "/" + chat_path
        route_map[chat_path] = (pid, style)

    # If no manifests, register default OpenAI and Anthropic paths
    if not route_map:
        route_map["/v1/chat/completions"] = ("openai", "openai")
        route_map["/chat/completions"] = ("openai", "openai")
        route_map["/v1/messages"] = ("anthropic", "anthropic")
        route_map["/messages"] = ("anthropic", "anthropic")

    async def handle_chat(request: Request, path: str = ""):
        if config.ERROR_RATE > 0 and random.random() < config.ERROR_RATE:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=random.choice([429, 500, 503]),
                content={"error": {"message": "Mock error for testing"}},
            )
        if config.RESPONSE_DELAY > 0:
            await asyncio.sleep(config.RESPONSE_DELAY)

        try:
            body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
        except Exception:
            body = {}
        if not isinstance(body, dict):
            body = {}
        model = body.get("model", "gpt-4o")
        stream = body.get("stream", False)
        content = config.MOCK_CONTENT
        usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}

        # Find matching style by path
        style = "openai"
        req_path = path or str(request.url.path)
        for route_path, (_, s) in route_map.items():
            if req_path == route_path or req_path.endswith(route_path):
                style = s
                break
        # Infer from path if not in map
        if "/messages" in req_path:
            style = "anthropic"

        if style == "anthropic":
            resp = _anthropic_response(content, model, stream, usage)
        else:
            resp = _openai_response(content, model, stream, usage)

        if stream:
            import json
            def gen():
                for chunk in resp:
                    yield f"data: {json.dumps(chunk)}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(gen(), media_type="text/event-stream")
        return resp

    @router.api_route("/v1/chat/completions", methods=["POST"])
    async def openai_chat(request: Request):
        return await handle_chat(request, "/v1/chat/completions")

    @router.api_route("/chat/completions", methods=["POST"])
    async def openai_chat_alt(request: Request):
        return await handle_chat(request, "/chat/completions")

    @router.api_route("/v1/messages", methods=["POST"])
    async def anthropic_chat(request: Request):
        return await handle_chat(request, "/v1/messages")

    @router.api_route("/messages", methods=["POST"])
    async def anthropic_chat_alt(request: Request):
        return await handle_chat(request, "/messages")

    return router
