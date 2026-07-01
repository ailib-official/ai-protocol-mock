"""Protocol-aware mock response generation (MOCK-001-R2).

按 X-Mock-* 测试头与请求体生成分支化 chat 响应。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

Style = Literal["openai", "anthropic", "gemini"]

_REASONING_TEXT = "mock reasoning trace"
_STRUCTURED_OBJECT = {"result": "mock_structured_output"}
_STRUCTURED_SCHEMA = {"count": 3, "items": ["a", "b", "c"]}


@dataclass(frozen=True)
class ChatMockContext:
    """Inputs derived from HTTP request for chat mock generation."""

    style: Style
    model: str
    content: str
    stream: bool
    reasoning: bool
    tool_mode: str | None
    tool_depth: int
    usage_format: str | None
    messages: list[Any]
    response_format: dict[str, Any] | None


def parse_chat_context(
    *,
    style: Style,
    headers: dict[str, str],
    body: dict[str, Any],
    default_content: str,
) -> ChatMockContext:
    tool_header = headers.get("x-mock-tool-calls", "").strip().lower()
    tool_mode = tool_header if tool_header in {"1", "true", "yes", "parallel", "recursive"} else None
    if tool_mode in {"1", "true", "yes"}:
        tool_mode = "single"

    depth_raw = headers.get("x-mock-tool-depth", "1")
    try:
        tool_depth = max(1, int(depth_raw))
    except ValueError:
        tool_depth = 1

    rf = body.get("response_format")
    response_format = rf if isinstance(rf, dict) else None

    messages = body.get("messages")
    if not isinstance(messages, list):
        messages = []

    return ChatMockContext(
        style=style,
        model=str(body.get("model", "gpt-4o")),
        content=headers.get("x-mock-content") or default_content,
        stream=bool(body.get("stream", False)),
        reasoning=headers.get("x-mock-reasoning", "").lower() in {"1", "true", "yes"},
        tool_mode=tool_mode,
        tool_depth=tool_depth,
        usage_format=headers.get("x-mock-usage-format"),
        messages=messages,
        response_format=response_format,
    )


def generate_chat_response(ctx: ChatMockContext) -> dict[str, Any] | list[dict[str, Any]]:
    """Build sync or streaming chat payload for the resolved wire style."""
    if ctx.tool_mode == "parallel":
        return _openai_parallel_tools(ctx)
    if ctx.tool_mode == "recursive":
        return _openai_recursive_tools(ctx)
    if ctx.tool_mode == "single":
        if ctx.style == "anthropic":
            return _anthropic_tool_call_response(ctx.model)
        if ctx.style == "gemini":
            return _gemini_tool_call_response()
        return _openai_tool_call_response(ctx.model)

    if ctx.response_format and ctx.style == "openai":
        return _openai_structured_response(ctx)

    if ctx.reasoning:
        if ctx.style == "anthropic":
            return _anthropic_reasoning_response(ctx)
        return _openai_reasoning_response(ctx)

    usage = _usage_for_style(ctx)
    if ctx.style == "anthropic":
        return _anthropic_plain_response(ctx, usage)
    if ctx.style == "gemini":
        return _gemini_plain_response(ctx)
    return _openai_plain_response(ctx, usage)


def openai_stream_chunks(ctx: ChatMockContext, base_chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Limit stream length when simulating interruption."""
    if ctx.stream and len(base_chunks) > 3:
        return base_chunks[:3]
    return base_chunks


def _usage_for_style(ctx: ChatMockContext) -> dict[str, Any]:
    content_tokens = max(1, len(ctx.content.split()))
    if ctx.style == "anthropic" or ctx.usage_format == "anthropic":
        return {
            "input_tokens": 10,
            "output_tokens": content_tokens,
            "cache_creation_input_tokens": 4,
            "cache_read_input_tokens": 2,
        }
    usage: dict[str, Any] = {
        "prompt_tokens": 10,
        "completion_tokens": content_tokens,
        "total_tokens": 10 + content_tokens,
    }
    if ctx.usage_format == "openai" or ctx.reasoning:
        usage["completion_tokens_details"] = {"reasoning_tokens": 5, "accepted_prediction_tokens": 0}
    return usage


def _openai_plain_response(ctx: ChatMockContext, usage: dict[str, Any]) -> dict[str, Any] | list[dict[str, Any]]:
    if ctx.stream:
        chunks = []
        for char in ctx.content:
            chunks.append(
                {
                    "id": "chatcmpl-mock",
                    "object": "chat.completion.chunk",
                    "created": 1699012345,
                    "model": ctx.model,
                    "choices": [{"index": 0, "delta": {"content": char}, "finish_reason": None}],
                }
            )
        chunks.append(
            {
                "id": "chatcmpl-mock",
                "object": "chat.completion.chunk",
                "created": 1699012345,
                "model": ctx.model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }
        )
        return chunks
    return {
        "id": "chatcmpl-mock",
        "object": "chat.completion",
        "created": 1699012345,
        "model": ctx.model,
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": ctx.content}, "finish_reason": "stop"}
        ],
        "usage": usage,
    }


def _openai_reasoning_response(ctx: ChatMockContext) -> dict[str, Any] | list[dict[str, Any]]:
    usage = _usage_for_style(ctx)
    if ctx.stream:
        chunks = [
            {
                "id": "chatcmpl-mock",
                "object": "chat.completion.chunk",
                "created": 1699012345,
                "model": ctx.model,
                "choices": [
                    {"index": 0, "delta": {"reasoning_content": _REASONING_TEXT}, "finish_reason": None}
                ],
            },
            {
                "id": "chatcmpl-mock",
                "object": "chat.completion.chunk",
                "created": 1699012345,
                "model": ctx.model,
                "choices": [{"index": 0, "delta": {"content": ctx.content}, "finish_reason": None}],
            },
            {
                "id": "chatcmpl-mock",
                "object": "chat.completion.chunk",
                "created": 1699012345,
                "model": ctx.model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            },
        ]
        return chunks
    return {
        "id": "chatcmpl-mock",
        "object": "chat.completion",
        "created": 1699012345,
        "model": ctx.model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": ctx.content,
                    "reasoning_content": _REASONING_TEXT,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": usage,
    }


def _openai_structured_response(ctx: ChatMockContext) -> dict[str, Any]:
    rf_type = ctx.response_format.get("type") if ctx.response_format else None
    payload = _STRUCTURED_SCHEMA if rf_type == "json_schema" else _STRUCTURED_OBJECT
    return {
        "id": "chatcmpl-mock",
        "object": "chat.completion",
        "created": 1699012345,
        "model": ctx.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": json.dumps(payload)},
                "finish_reason": "stop",
            }
        ],
        "usage": _usage_for_style(ctx),
    }


def _openai_tool_call_response(model: str) -> dict[str, Any]:
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
                                "name": "get_weather",
                                "arguments": json.dumps({"city": "Tokyo"}),
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


def _openai_parallel_tools(ctx: ChatMockContext) -> dict[str, Any] | list[dict[str, Any]]:
    tool_calls = [
        {
            "id": "call_mock_1",
            "type": "function",
            "function": {"name": "get_weather", "arguments": json.dumps({"city": "Tokyo"})},
        },
        {
            "id": "call_mock_2",
            "type": "function",
            "function": {"name": "get_time", "arguments": json.dumps({"tz": "UTC"})},
        },
    ]
    if ctx.stream:
        return [
            {
                "id": "chatcmpl-mock",
                "object": "chat.completion.chunk",
                "created": 1699012345,
                "model": ctx.model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"tool_calls": [tool_calls[0]]},
                        "finish_reason": None,
                    }
                ],
            },
            {
                "id": "chatcmpl-mock",
                "object": "chat.completion.chunk",
                "created": 1699012345,
                "model": ctx.model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"tool_calls": [tool_calls[1]]},
                        "finish_reason": None,
                    }
                ],
            },
            {
                "id": "chatcmpl-mock",
                "object": "chat.completion.chunk",
                "created": 1699012345,
                "model": ctx.model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
            },
        ]
    return {
        "id": "chatcmpl-mock",
        "object": "chat.completion",
        "created": 1699012345,
        "model": ctx.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "tool_calls": tool_calls},
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
    }


def _openai_recursive_tools(ctx: ChatMockContext) -> dict[str, Any]:
    has_tool_results = any(isinstance(m, dict) and m.get("role") == "tool" for m in ctx.messages)
    if has_tool_results or ctx.tool_depth <= 1:
        return {
            "id": "chatcmpl-mock",
            "object": "chat.completion",
            "created": 1699012345,
            "model": ctx.model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": ctx.content},
                    "finish_reason": "stop",
                }
            ],
            "usage": _usage_for_style(ctx),
        }
    return {
        "id": "chatcmpl-mock",
        "object": "chat.completion",
        "created": 1699012345,
        "model": ctx.model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call_step_1",
                            "type": "function",
                            "function": {
                                "name": "step_1_tool",
                                "arguments": json.dumps({"step": 1}),
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


def _anthropic_plain_response(ctx: ChatMockContext, usage: dict[str, Any]) -> dict[str, Any] | list[dict[str, Any]]:
    if ctx.stream:
        chunks = [
            {
                "type": "message_start",
                "message": {
                    "id": "msg-mock",
                    "type": "message",
                    "role": "assistant",
                    "content": [],
                    "model": ctx.model,
                    "stop_reason": None,
                    "usage": {"input_tokens": 10, "output_tokens": 0},
                },
            },
            {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        ]
        for char in ctx.content:
            chunks.append(
                {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": char}}
            )
        chunks.extend([{"type": "content_block_stop", "index": 0}, {"type": "message_stop"}])
        return chunks
    return {
        "id": "msg-mock",
        "type": "message",
        "role": "assistant",
        "model": ctx.model,
        "content": [{"type": "text", "text": ctx.content}],
        "stop_reason": "end_turn",
        "usage": usage,
    }


def _anthropic_reasoning_response(ctx: ChatMockContext) -> dict[str, Any] | list[dict[str, Any]]:
    usage = _usage_for_style(ctx)
    if ctx.stream:
        return [
            {
                "type": "message_start",
                "message": {
                    "id": "msg-mock",
                    "type": "message",
                    "role": "assistant",
                    "content": [],
                    "model": ctx.model,
                    "stop_reason": None,
                    "usage": usage,
                },
            },
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "thinking", "thinking": ""},
            },
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "thinking_delta", "thinking": _REASONING_TEXT},
            },
            {"type": "content_block_stop", "index": 0},
            {
                "type": "content_block_start",
                "index": 1,
                "content_block": {"type": "text", "text": ""},
            },
            {
                "type": "content_block_delta",
                "index": 1,
                "delta": {"type": "text_delta", "text": ctx.content},
            },
            {"type": "content_block_stop", "index": 1},
            {"type": "message_stop"},
        ]
    return {
        "id": "msg-mock",
        "type": "message",
        "role": "assistant",
        "model": ctx.model,
        "content": [
            {"type": "thinking", "thinking": _REASONING_TEXT},
            {"type": "text", "text": ctx.content},
        ],
        "stop_reason": "end_turn",
        "usage": usage,
    }


def _anthropic_tool_call_response(model: str) -> dict[str, Any]:
    return {
        "id": "msg-mock",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [
            {
                "type": "tool_use",
                "id": "toolu_mock",
                "name": "get_weather",
                "input": {"city": "Tokyo"},
            }
        ],
        "stop_reason": "tool_use",
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


def _gemini_plain_response(ctx: ChatMockContext) -> dict[str, Any] | list[dict[str, Any]]:
    if ctx.stream:
        mid = max(1, len(ctx.content) // 2)
        return [
            {
                "candidates": [
                    {
                        "index": 0,
                        "content": {"parts": [{"text": ctx.content[:mid]}]},
                        "finishReason": None,
                    }
                ]
            },
            {
                "candidates": [
                    {
                        "index": 0,
                        "content": {"parts": [{"text": ctx.content[mid:]}]},
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 10,
                    "candidatesTokenCount": max(1, len(ctx.content.split())),
                    "totalTokenCount": 10 + max(1, len(ctx.content.split())),
                },
            },
        ]
    return {
        "candidates": [
            {
                "index": 0,
                "content": {"parts": [{"text": ctx.content}]},
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 10,
            "candidatesTokenCount": max(1, len(ctx.content.split())),
            "totalTokenCount": 10 + max(1, len(ctx.content.split())),
        },
        "modelVersion": ctx.model,
    }


def _gemini_tool_call_response() -> dict[str, Any]:
    return {
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
