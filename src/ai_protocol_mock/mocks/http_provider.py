"""HTTP Provider Mock - manifest-driven, supports OpenAI and non-OpenAI formats.

HTTP Provider Mock 模块：基于 manifest 驱动的 HTTP 模拟，支持 OpenAI 及 Anthropic 等格式。
"""

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
    """Load all provider manifests from directory. Supports v1 and v2 providers."""
    manifests: dict[str, dict[str, Any]] = {}
    for rel in ["v1/providers", "v2/providers", "providers"]:
        providers_dir = manifest_dir / rel
        if not providers_dir.exists():
            continue
        for f in providers_dir.glob("*.yaml"):
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8"))
                if data and isinstance(data, dict):
                    pid = data.get("id", f.stem)
                    manifests[pid] = data
            except Exception:
                pass
    return manifests


def _get_chat_path(manifest: dict[str, Any]) -> str:
    """Extract chat endpoint path from manifest. Supports v1 and v2 formats."""
    ep = manifest.get("endpoints") or manifest.get("endpoint") or {}
    if not isinstance(ep, dict):
        return "/chat/completions"
    chat = ep.get("chat")
    if isinstance(chat, dict):
        return chat.get("path", "/chat/completions") or "/chat/completions"
    if isinstance(chat, str) and chat:
        return chat if chat.startswith("/") else f"/{chat}"
    return "/chat/completions"


def _detect_api_style(manifest: dict[str, Any]) -> str:
    """Detect API style from manifest. Returns 'openai' or 'anthropic'."""
    chat_path = _get_chat_path(manifest)
    # Anthropic uses /messages, OpenAI uses /chat/completions
    if "/messages" in chat_path or chat_path.endswith("messages"):
        return "anthropic"
    return "openai"


def get_provider_contracts(manifest_dir: Path | None = None) -> list[dict[str, Any]]:
    """Build provider contract list from manifests for runtime compatibility.
    Returns list of {provider_id, api_style, chat_path, name} per provider.
    """
    mdir = manifest_dir or config.MANIFEST_DIR
    manifests = _load_manifests(mdir)
    contracts = []
    for pid, m in manifests.items():
        style = _detect_api_style(m)
        chat_path = _get_chat_path(m)
        contracts.append(
            {
                "provider_id": pid,
                "api_style": "openai_compatible" if style == "openai" else "anthropic_messages",
                "chat_path": chat_path,
                "name": m.get("name", pid),
            }
        )
    if not contracts:
        contracts = [
            {
                "provider_id": "openai",
                "api_style": "openai_compatible",
                "chat_path": "/chat/completions",
                "name": "OpenAI",
            },
            {
                "provider_id": "anthropic",
                "api_style": "anthropic_messages",
                "chat_path": "/messages",
                "name": "Anthropic",
            },
        ]
    return contracts


def _openai_response(content: str, model: str, stream: bool, usage: dict | None = None) -> dict | list[dict]:
    """Generate OpenAI-format response."""
    if stream:
        chunks = []
        for char in content:
            chunks.append(
                {
                    "id": "chatcmpl-mock",
                    "object": "chat.completion.chunk",
                    "created": 1699012345,
                    "model": model,
                    "choices": [{"index": 0, "delta": {"content": char}, "finish_reason": None}],
                }
            )
        chunks.append(
            {
                "id": "chatcmpl-mock",
                "object": "chat.completion.chunk",
                "created": 1699012345,
                "model": model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }
        )
        return chunks
    resp = {
        "id": "chatcmpl-mock",
        "object": "chat.completion",
        "created": 1699012345,
        "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
    }
    if usage:
        resp["usage"] = usage
    else:
        resp["usage"] = {
            "prompt_tokens": 10,
            "completion_tokens": len(content.split()),
            "total_tokens": 10 + len(content.split()),
        }
    return resp


def _openai_tool_call_response(
    tool_name: str = "get_weather",
    tool_args: dict | None = None,
    model: str = "gpt-4o",
) -> dict:
    """Generate OpenAI-format response with tool_calls."""
    if tool_args is None:
        tool_args = {"city": "Tokyo"}
    import json
    return {
        "id": "chatcmpl-mock",
        "object": "chat.completion",
        "created": 1699012345,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call_mock",
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": json.dumps(tool_args),
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


def _anthropic_tool_call_response(
    tool_name: str = "get_weather",
    tool_input: dict | None = None,
    model: str = "claude-3-5-sonnet-20241022",
) -> dict:
    """Generate Anthropic-format response with tool_use."""
    if tool_input is None:
        tool_input = {"city": "Tokyo"}
    return {
        "id": "msg-mock",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [
            {
                "type": "tool_use",
                "id": "toolu_mock",
                "name": tool_name,
                "input": tool_input,
            }
        ],
        "stop_reason": "tool_use",
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


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
        chunks.extend(
            [
                {"type": "content_block_stop", "index": 0},
                {"type": "message_stop"},
            ]
        )
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


def _gemini_response(content: str, model: str, stream: bool) -> dict | list[dict]:
    """Generate Gemini-format response for generateContent APIs."""
    if stream:
        return [
            {
                "candidates": [
                    {
                        "index": 0,
                        "content": {"parts": [{"text": content[: max(1, len(content) // 2)]}]},
                        "finishReason": None,
                    }
                ]
            },
            {
                "candidates": [
                    {
                        "index": 0,
                        "content": {"parts": [{"text": content[max(1, len(content) // 2) :]}]},
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 10,
                    "candidatesTokenCount": max(1, len(content.split())),
                    "totalTokenCount": 10 + max(1, len(content.split())),
                },
            },
        ]
    return {
        "candidates": [
            {
                "index": 0,
                "content": {"parts": [{"text": content}]},
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 10,
            "candidatesTokenCount": max(1, len(content.split())),
            "totalTokenCount": 10 + max(1, len(content.split())),
        },
        "modelVersion": model,
    }


def create_http_router(manifest_dir: Path | None = None) -> APIRouter:
    """Create FastAPI router with manifest-driven HTTP mock routes."""
    router = APIRouter()
    mdir = manifest_dir or config.MANIFEST_DIR
    manifests = _load_manifests(mdir)

    # Build route map: path -> (provider_id, api_style)
    route_map: dict[str, tuple[str, str]] = {}
    for pid, m in manifests.items():
        style = _detect_api_style(m)
        chat_path = _get_chat_path(m)
        # Register both bare path and /v1 prefix (OpenAI/Anthropic clients use /v1/...)
        for prefix in ("", "/v1"):
            full_path = f"{prefix}{chat_path}" if prefix else chat_path
            route_map[full_path] = (pid, style)

    # If no manifests, register default OpenAI and Anthropic paths
    if not route_map:
        route_map["/v1/chat/completions"] = ("openai", "openai")
        route_map["/chat/completions"] = ("openai", "openai")
        route_map["/v1/messages"] = ("anthropic", "anthropic")
        route_map["/messages"] = ("anthropic", "anthropic")

    async def handle_chat(request: Request, path: str = ""):
        from fastapi.responses import JSONResponse

        # Test control headers (for integration tests)
        mock_status = request.headers.get("x-mock-status")
        if mock_status:
            try:
                status_code = int(mock_status)
                if 400 <= status_code < 600:
                    return JSONResponse(
                        status_code=status_code,
                        content={"error": {"message": f"Mock error (X-Mock-Status={status_code})", "type": "mock_error"}},
                    )
            except ValueError:
                pass

        if config.ERROR_RATE > 0 and random.random() < config.ERROR_RATE:
            return JSONResponse(
                status_code=random.choice([429, 500, 503]),
                content={"error": {"message": "Mock error for testing"}},
            )
        if config.RESPONSE_DELAY > 0:
            await asyncio.sleep(config.RESPONSE_DELAY)

        try:
            body = (
                await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
            )
        except Exception:
            body = {}
        if not isinstance(body, dict):
            body = {}
        model = body.get("model", "gpt-4o")
        stream = body.get("stream", False)
        content = request.headers.get("x-mock-content") or config.MOCK_CONTENT
        mock_tool_calls = request.headers.get("x-mock-tool-calls", "").lower() in ("1", "true", "yes")

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
        elif ":generateContent" in req_path or ":streamGenerateContent" in req_path:
            style = "gemini"

        if mock_tool_calls:
            if style == "anthropic":
                resp = _anthropic_tool_call_response(model=model)
            elif style == "gemini":
                resp = {
                    "candidates": [
                        {
                            "index": 0,
                            "content": {
                                "parts": [
                                    {
                                        "functionCall": {
                                            "name": "get_weather",
                                            "args": {"city": "Tokyo"},
                                        }
                                    }
                                ]
                            },
                            "finishReason": "STOP",
                        }
                    ]
                }
            else:
                resp = _openai_tool_call_response(model=model)
            if stream:
                # Tool calls in streaming: emit as single chunk for simplicity
                import json
                def gen():
                    yield f"data: {json.dumps(resp)}\n\n"
                    yield "data: [DONE]\n\n"
                return StreamingResponse(gen(), media_type="text/event-stream")
            return resp

        usage = (
            {"input_tokens": 10, "output_tokens": len(content.split())}
            if style == "anthropic"
            else {
                "prompt_tokens": 10,
                "completion_tokens": len(content.split()),
                "total_tokens": 10 + len(content.split()),
            }
        )
        if style == "anthropic":
            resp = _anthropic_response(content, model, stream, usage)
        elif style == "gemini":
            resp = _gemini_response(content, model, stream)
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

    @router.api_route("/v1beta/models/{model_name}:generateContent", methods=["POST"])
    async def gemini_generate_content(request: Request, model_name: str):
        return await handle_chat(request, f"/v1beta/models/{model_name}:generateContent")

    @router.api_route("/v1beta/models/{model_name}:streamGenerateContent", methods=["POST"])
    async def gemini_stream_generate_content(request: Request, model_name: str):
        return await handle_chat(request, f"/v1beta/models/{model_name}:streamGenerateContent")

    # --- STT / TTS / Rerank mock endpoints (OpenAI/Cohere format) ---

    @router.api_route("/v1/audio/transcriptions", methods=["POST"])
    async def stt_transcriptions(request: Request):
        """Mock STT (OpenAI Whisper format). Returns {"text": "mock transcription"}."""
        if config.ERROR_RATE > 0 and random.random() < config.ERROR_RATE:
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=random.choice([429, 500, 503]),
                content={"error": {"message": "Mock STT error"}},
            )
        if config.RESPONSE_DELAY > 0:
            await asyncio.sleep(config.RESPONSE_DELAY)
        return {"text": "mock transcription from ai-protocol-mock"}

    @router.api_route("/v1/audio/speech", methods=["POST"])
    async def tts_speech(request: Request):
        """Mock TTS (OpenAI format). Returns minimal MP3 header bytes (mock audio)."""
        if config.ERROR_RATE > 0 and random.random() < config.ERROR_RATE:
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=random.choice([429, 500, 503]),
                content={"error": {"message": "Mock TTS error"}},
            )
        if config.RESPONSE_DELAY > 0:
            await asyncio.sleep(config.RESPONSE_DELAY)
        # Minimal valid MP3 frame header (13 bytes) for testing
        mock_audio = bytes([0xFF, 0xFB, 0x90, 0x00] + [0] * 9)
        from fastapi.responses import Response

        return Response(content=mock_audio, media_type="audio/mpeg")

    @router.api_route("/v2/rerank", methods=["POST"])
    async def rerank(request: Request):
        """Mock Rerank (Cohere v2 format). Returns results with index and relevance_score."""
        if config.ERROR_RATE > 0 and random.random() < config.ERROR_RATE:
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=random.choice([429, 500, 503]),
                content={"message": "Mock Rerank error"},
            )
        if config.RESPONSE_DELAY > 0:
            await asyncio.sleep(config.RESPONSE_DELAY)
        try:
            body = (
                await request.json()
                if request.headers.get("content-type", "").startswith("application/json")
                else {}
            )
        except Exception:
            body = {}
        if not isinstance(body, dict):
            body = {}
        documents = body.get("documents", [])
        top_n = body.get("top_n", len(documents))
        results = [
            {"index": i, "relevance_score": 1.0 - (i * 0.1)}
            for i in range(min(top_n, len(documents)))
        ]
        # Cohere v2 format: results, id, meta (api_version, billed_units)
        return {
            "results": results,
            "id": "mock-rerank-id",
            "meta": {
                "api_version": {"version": "2", "is_experimental": False},
                "billed_units": {"search_units": 1},
            },
        }

    return router
