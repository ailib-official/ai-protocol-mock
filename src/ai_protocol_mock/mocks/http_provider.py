"""HTTP Provider Mock - manifest-driven, supports OpenAI and non-OpenAI formats.

HTTP Provider Mock 模块：基于 manifest 驱动的 HTTP 模拟，支持 OpenAI 及 Anthropic 等格式。
"""

from __future__ import annotations

import asyncio
import random
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from ai_protocol_mock.config import config
from ai_protocol_mock.engine.errors import apply_mock_error, is_stream_interrupt
from ai_protocol_mock.engine.generator import generate_chat_response, openai_stream_chunks, parse_chat_context
from ai_protocol_mock.engine.resolver import ContractResolver
from ai_protocol_mock.engine.stream import StreamEncoder, resolve_request_path


def get_provider_contracts(manifest_dir: Path | None = None) -> list[dict[str, Any]]:
    """Build provider contract list from manifests for runtime compatibility."""
    mdir = manifest_dir or config.MANIFEST_DIR
    resolver = ContractResolver(mdir)
    contracts = resolver.list_provider_summaries()
    if contracts:
        return contracts
    return [
        {
            "provider_id": "openai",
            "api_style": "openai_compatible",
            "chat_path": "/chat/completions",
            "name": "OpenAI",
            "has_capability_profile": False,
            "capability_profile_phase": None,
            "has_ios_dimensions": False,
        },
        {
            "provider_id": "anthropic",
            "api_style": "anthropic_messages",
            "chat_path": "/messages",
            "name": "Anthropic",
            "has_capability_profile": False,
            "capability_profile_phase": None,
            "has_ios_dimensions": False,
        },
    ]


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
    resolver = ContractResolver(mdir)
    manifests = dict(resolver.manifest_registry.items())

    # In-memory async job registry for deterministic polling simulation.
    # Key: job id, Value: {"status": str, "polls": int, "created_at": str, "provider": str}
    video_jobs: dict[str, dict[str, Any]] = {}
    terminal_states = {"succeeded", "failed", "cancelled"}

    # Build route map: path -> (provider_id, response_handler)
    route_map: dict[str, tuple[str, str]] = {}
    for pid, _m in manifests.items():
        try:
            res = resolver.resolve(pid)
        except KeyError:
            continue
        if res.source == "manifest_rerank":
            continue
        style = res.response_handler()
        chat_path = res.chat_path
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

    async def _apply_test_controls(request: Request) -> Response | None:
        """Apply generic test controls from headers.

        Supported headers:
        - X-Mock-Status: force HTTP status with JSON error body
        - X-Mock-Timeout-Ms: sleep for given milliseconds before response
        - X-Mock-Invalid-Content-Type: return text/plain content intentionally
        """
        mock_status = request.headers.get("x-mock-status")
        if mock_status:
            try:
                status_code = int(mock_status)
                if 400 <= status_code < 600:
                    return JSONResponse(
                        status_code=status_code,
                        content={
                            "error": {"message": f"Mock error (X-Mock-Status={status_code})", "type": "mock_error"}
                        },
                    )
            except ValueError:
                pass

        timeout_ms = request.headers.get("x-mock-timeout-ms")
        if timeout_ms:
            try:
                delay = max(0, int(timeout_ms)) / 1000.0
                await asyncio.sleep(delay)
            except ValueError:
                pass

        if request.headers.get("x-mock-invalid-content-type", "").lower() in {"1", "true", "yes"}:
            return Response(content="mock-invalid-content-type", media_type="text/plain")

        return None

    async def handle_chat(request: Request, path: str = ""):

        try:
            body = (
                await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
            )
        except Exception:
            body = {}
        if not isinstance(body, dict):
            body = {}
        stream = bool(body.get("stream", False))

        mock_error = apply_mock_error(request, stream=stream)
        if mock_error is not None and not is_stream_interrupt(mock_error):
            return mock_error

        controlled = await _apply_test_controls(request)
        if controlled is not None:
            return controlled

        if config.ERROR_RATE > 0 and random.random() < config.ERROR_RATE:
            return JSONResponse(
                status_code=random.choice([429, 500, 503]),
                content={"error": {"message": "Mock error for testing"}},
            )
        if config.RESPONSE_DELAY > 0:
            await asyncio.sleep(config.RESPONSE_DELAY)

        req_path = path or str(request.url.path)
        resolution = resolve_request_path(resolver, route_map, req_path)
        style = resolution.response_handler()

        ctx = parse_chat_context(
            style=style,  # type: ignore[arg-type]
            headers={k.lower(): v for k, v in request.headers.items()},
            body=body,
            default_content=config.MOCK_CONTENT,
        )
        resp = generate_chat_response(ctx)

        if is_stream_interrupt(mock_error):
            if style == "openai" and isinstance(resp, list):
                resp = openai_stream_chunks(ctx, resp)
            elif style == "openai":
                resp = openai_stream_chunks(
                    ctx,
                    [
                        {
                            "id": "chatcmpl-mock",
                            "object": "chat.completion.chunk",
                            "created": 1699012345,
                            "model": ctx.model,
                            "choices": [{"index": 0, "delta": {"content": "x"}, "finish_reason": None}],
                        }
                    ],
                )

        if stream:
            encoder = StreamEncoder(resolution)
            chunks = resp if isinstance(resp, list) else [resp]

            def gen():
                yield from encoder.encode_lines(chunks, emit_terminal=not is_stream_interrupt(mock_error))

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
        controlled = await _apply_test_controls(request)
        if controlled is not None:
            return controlled
        if config.ERROR_RATE > 0 and random.random() < config.ERROR_RATE:
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
        controlled = await _apply_test_controls(request)
        if controlled is not None:
            return controlled
        if config.ERROR_RATE > 0 and random.random() < config.ERROR_RATE:
            return JSONResponse(
                status_code=random.choice([429, 500, 503]),
                content={"error": {"message": "Mock TTS error"}},
            )
        if config.RESPONSE_DELAY > 0:
            await asyncio.sleep(config.RESPONSE_DELAY)
        # Minimal valid MP3 frame header (13 bytes) for testing
        mock_audio = bytes([0xFF, 0xFB, 0x90, 0x00] + [0] * 9)
        return Response(content=mock_audio, media_type="audio/mpeg")

    @router.api_route("/v2/rerank", methods=["POST"])
    async def rerank(request: Request):
        """Mock Rerank (Cohere v2 format). Returns results with index and relevance_score."""
        controlled = await _apply_test_controls(request)
        if controlled is not None:
            return controlled
        if config.ERROR_RATE > 0 and random.random() < config.ERROR_RATE:
            return JSONResponse(
                status_code=random.choice([429, 500, 503]),
                content={"message": "Mock Rerank error"},
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
        documents = body.get("documents", [])
        top_n = body.get("top_n", len(documents))
        results = [{"index": i, "relevance_score": 1.0 - (i * 0.1)} for i in range(min(top_n, len(documents)))]
        # Cohere v2 format: results, id, meta (api_version, billed_units)
        return {
            "results": results,
            "id": "mock-rerank-id",
            "meta": {
                "api_version": {"version": "2", "is_experimental": False},
                "billed_units": {"search_units": 1},
            },
        }

    @router.api_route("/v1/video/generations", methods=["POST"])
    async def video_generations(request: Request):
        """Mock video generation endpoint with sync and async-polling modes."""
        controlled = await _apply_test_controls(request)
        if controlled is not None:
            return controlled
        if config.ERROR_RATE > 0 and random.random() < config.ERROR_RATE:
            return JSONResponse(
                status_code=random.choice([429, 500, 503]),
                content={"error": {"message": "Mock video generation error", "type": "video_error"}},
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

        async_mode = bool(body.get("async", True))
        model = str(body.get("model", "video-gen-1"))
        provider = str(body.get("provider", "mock"))
        prompt = str(body.get("prompt", "mock video prompt"))
        requested_terminal = request.headers.get("x-mock-video-terminal") or body.get("terminal_state") or "succeeded"
        if requested_terminal not in terminal_states:
            requested_terminal = "succeeded"

        if not async_mode:
            return {
                "id": f"vid_{uuid4().hex[:12]}",
                "status": "succeeded",
                "model": model,
                "provider": provider,
                "prompt": prompt,
                "output": {
                    "url": "https://example.com/mock-video.mp4",
                    "content_type": "video/mp4",
                    "duration_seconds": 4,
                },
                "created_at": datetime.now(UTC).isoformat(),
            }

        job_id = f"job_{uuid4().hex[:12]}"
        video_jobs[job_id] = {
            "status": "queued",
            "polls": 0,
            "provider": provider,
            "model": model,
            "prompt": prompt,
            "terminal_state": requested_terminal,
            "created_at": datetime.now(UTC).isoformat(),
        }
        return JSONResponse(
            status_code=202,
            content={
                "id": job_id,
                "status": "queued",
                "poll_url": f"/v1/video/generations/{job_id}",
                "created_at": video_jobs[job_id]["created_at"],
            },
        )

    @router.api_route("/v1/video/generations/{job_id}", methods=["GET"])
    async def get_video_generation_status(job_id: str, request: Request):
        """Poll mock video generation job status."""
        controlled = await _apply_test_controls(request)
        if controlled is not None:
            return controlled
        job = video_jobs.get(job_id)
        if job is None:
            return JSONResponse(
                status_code=404,
                content={"error": {"message": f"Video job '{job_id}' not found", "type": "not_found"}},
            )

        job["polls"] = int(job.get("polls", 0)) + 1
        current_status = str(job.get("status", "queued"))
        if current_status not in terminal_states:
            if job["polls"] == 1:
                job["status"] = "running"
            elif job["polls"] >= 2:
                job["status"] = job.get("terminal_state", "succeeded")

        response: dict[str, Any] = {
            "id": job_id,
            "status": job["status"],
            "provider": job["provider"],
            "model": job["model"],
            "created_at": job["created_at"],
            "updated_at": datetime.now(UTC).isoformat(),
            "polls": job["polls"],
            "terminal_state": job.get("terminal_state", "succeeded"),
        }
        if job["status"] == "succeeded":
            response["output"] = {
                "url": "https://example.com/mock-video.mp4",
                "content_type": "video/mp4",
                "duration_seconds": 4,
                "completed_at": datetime.now(UTC).isoformat(),
                "elapsed_ms": int((time.time() * 1000) % 100000),
            }
        elif job["status"] == "failed":
            response["error"] = {
                "code": "video_generation_failed",
                "message": "Mock video generation failed at terminal state",
            }
        elif job["status"] == "cancelled":
            response["cancellation"] = {
                "reason": "mock_cancelled_for_test",
                "cancelled_at": datetime.now(UTC).isoformat(),
            }
        return response

    return router
