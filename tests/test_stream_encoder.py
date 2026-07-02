"""Tests for MOCK-001-R2b StreamEncoder and event_map-driven SSE framing."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_protocol_mock.engine.resolver import ContractResolver
from ai_protocol_mock.engine.stream import StreamEncoder, match_event_map_emit, resolve_request_path


@pytest.fixture
def resolver() -> ContractResolver:
    manifest_dir = Path(__file__).resolve().parents[1] / "manifests"
    return ContractResolver(manifest_dir)


def test_openai_stream_event_sequence(resolver: ContractResolver) -> None:
    """OpenAI SSE uses data: prefix and [DONE] terminal from manifest decoder."""
    res = resolver.resolve("openai")
    encoder = StreamEncoder(res)
    chunks = [
        {
            "id": "chatcmpl-mock",
            "object": "chat.completion.chunk",
            "choices": [{"index": 0, "delta": {"content": "Hi"}, "finish_reason": None}],
        },
        {
            "id": "chatcmpl-mock",
            "object": "chat.completion.chunk",
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        },
    ]
    lines = list(encoder.encode_lines(chunks))
    text = "".join(lines)
    assert text.startswith("data: ")
    assert "data: [DONE]" in text
    emits = encoder.matched_emit_types(chunks)
    assert emits[0] == "PartialContentDelta"
    assert emits[1] == "StreamEnd"


def test_anthropic_stream_no_done_marker(resolver: ContractResolver) -> None:
    """Anthropic SSE uses event: lines and no OpenAI [DONE] marker."""
    res = resolver.resolve("anthropic")
    encoder = StreamEncoder(res)
    chunks = [
        {"type": "message_start", "message": {"id": "msg-mock", "type": "message"}},
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "x"},
        },
        {"type": "message_stop"},
    ]
    text = "".join(encoder.encode_lines(chunks))
    assert "event: message_start" in text
    assert "event: content_block_delta" in text
    assert "event: message_stop" in text
    assert "data: [DONE]" not in text
    emits = encoder.matched_emit_types(chunks)
    assert emits[1] == "PartialContentDelta"


def test_anthropic_reasoning_delta_matches_event_map(resolver: ContractResolver) -> None:
    res = resolver.resolve("anthropic")
    chunk = {
        "type": "content_block_delta",
        "index": 0,
        "delta": {"type": "thinking_delta", "thinking": "trace"},
    }
    assert match_event_map_emit(chunk, res.event_map or [], "anthropic_sse") == "ThinkingDelta"


def test_resolve_request_path_openai(resolver: ContractResolver) -> None:
    route_map = {"/v1/chat/completions": ("openai", "openai")}
    res = resolve_request_path(resolver, route_map, "/v1/chat/completions")
    assert res.provider_id == "openai"
    assert res.response_handler() == "openai"


def test_resolve_request_path_anthropic(resolver: ContractResolver) -> None:
    route_map = {"/v1/messages": ("anthropic", "anthropic")}
    res = resolve_request_path(resolver, route_map, "/v1/messages")
    assert res.provider_id == "anthropic"
    assert res.response_handler() == "anthropic"


def test_resolve_request_path_gemini_generate(resolver: ContractResolver) -> None:
    route_map: dict[str, tuple[str, str]] = {}
    res = resolve_request_path(
        resolver,
        route_map,
        "/v1beta/models/gemini-2.0-flash:streamGenerateContent",
    )
    assert res.provider_id in {"google", "gemini"}
    assert res.response_handler() == "gemini"


def test_openai_stream_chunks_parseable(resolver: ContractResolver) -> None:
    """Each data line (except terminal) is valid JSON matching event_map."""
    res = resolver.resolve("openai")
    encoder = StreamEncoder(res)
    chunks = [
        {
            "choices": [{"index": 0, "delta": {"content": "a"}, "finish_reason": None}],
        },
    ]
    for line in encoder.encode_lines(chunks, emit_terminal=False):
        if line.startswith("data: ") and line.strip() != "data: [DONE]":
            payload = json.loads(line[len("data: ") :].strip())
            assert isinstance(payload, dict)
