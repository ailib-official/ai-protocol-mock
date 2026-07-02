"""SSE stream encoding driven by manifest streaming.decoder (MOCK-001-R2b).

按 ProviderContract / manifest `streaming.decoder` 与 `event_map` 生成 SSE 帧。
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from typing import Any

from ai_protocol_mock.engine.resolver import ContractResolver, ProviderResolution

# Anthropic wire events required for framing but absent from event_map.
_ANTHROPIC_FRAMING_TYPES = frozenset(
    {
        "message_start",
        "content_block_start",
        "content_block_stop",
        "message_stop",
        "ping",
    }
)


class StreamEncoder:
    """Encode wire-format chunk dicts as SSE lines per manifest decoder."""

    def __init__(self, resolution: ProviderResolution) -> None:
        self._resolution = resolution
        decoder = _decoder_config(resolution.manifest)
        self._format = str(decoder.get("format", "sse"))
        prefix = decoder.get("prefix", "data: ")
        self._prefix = prefix if isinstance(prefix, str) else "data: "
        self._done_signal = resolution.streaming_done_signal
        if self._done_signal is None and self._format == "sse":
            done = decoder.get("done_signal")
            self._done_signal = done if isinstance(done, str) else "[DONE]"

    @property
    def resolution(self) -> ProviderResolution:
        return self._resolution

    def encode_lines(
        self,
        chunks: list[dict[str, Any]],
        *,
        emit_terminal: bool = True,
    ) -> Iterator[str]:
        """Yield SSE lines for each chunk; optional manifest terminal signal."""
        for chunk in chunks:
            yield from _encode_chunk(chunk, self._format, self._prefix)

        if emit_terminal and self._done_signal and not _terminal_in_chunks(chunks, self._done_signal):
            yield f"{self._prefix}{self._done_signal}\n\n"

    def matched_emit_types(self, chunks: list[dict[str, Any]]) -> list[str | None]:
        """Return event_map emit type per chunk (None when framing-only or unmatched)."""
        event_map = self._resolution.event_map
        if not event_map:
            return [None] * len(chunks)
        return [match_event_map_emit(chunk, event_map, self._format) for chunk in chunks]


def resolve_request_path(
    resolver: ContractResolver,
    route_map: dict[str, tuple[str, str]],
    req_path: str,
) -> ProviderResolution:
    """Resolve provider from request path using route_map (manifest-driven, not path heuristics)."""
    provider_id: str | None = None
    best_len = -1
    for route_path, (pid, _style) in route_map.items():
        if req_path == route_path or req_path.endswith(route_path):
            if len(route_path) > best_len:
                provider_id = pid
                best_len = len(route_path)

    if provider_id is None:
        if ":generateContent" in req_path or ":streamGenerateContent" in req_path:
            registry = resolver.manifest_registry
            if registry.get("google"):
                provider_id = "google"
            elif registry.get("gemini"):
                provider_id = "gemini"
        elif "/messages" in req_path:
            provider_id = "anthropic"
        else:
            provider_id = "openai"

    return resolver.resolve(provider_id)


def match_event_map_emit(
    chunk: dict[str, Any],
    event_map: list[dict[str, Any]],
    wire_format: str,
) -> str | None:
    """Return first matching emit type, or None for framing-only chunks."""
    if wire_format == "anthropic_sse":
        chunk_type = chunk.get("type")
        if isinstance(chunk_type, str) and chunk_type in _ANTHROPIC_FRAMING_TYPES:
            if chunk_type == "message_stop":
                return "StreamEnd"
            return None

    for rule in event_map:
        if not isinstance(rule, dict):
            continue
        if _chunk_matches_rule(chunk, rule):
            emit = rule.get("emit")
            return emit if isinstance(emit, str) else None
    return None


def _decoder_config(manifest: dict[str, Any]) -> dict[str, Any]:
    streaming = manifest.get("streaming")
    if isinstance(streaming, dict):
        decoder = streaming.get("decoder")
        if isinstance(decoder, dict):
            return decoder
    return {}


def _encode_chunk(chunk: dict[str, Any], fmt: str, prefix: str) -> Iterator[str]:
    if fmt == "anthropic_sse":
        event_type = chunk.get("type")
        if isinstance(event_type, str):
            yield f"event: {event_type}\n"
        yield f"{prefix}{json.dumps(chunk, separators=(',', ':'))}\n\n"
    else:
        yield f"{prefix}{json.dumps(chunk, separators=(',', ':'))}\n\n"


def _terminal_in_chunks(chunks: list[dict[str, Any]], done_signal: str) -> bool:
    if done_signal == "message_stop":
        return any(isinstance(c.get("type"), str) and c["type"] == "message_stop" for c in chunks)
    if done_signal == "[DONE]":
        return False
    return False


def _chunk_matches_rule(chunk: dict[str, Any], rule: dict[str, Any]) -> bool:
    match_expr = rule.get("match")
    if not isinstance(match_expr, str):
        return False
    if "==" in match_expr or "&&" in match_expr:
        return _eval_predicate(chunk, match_expr)
    if match_expr.startswith("$."):
        val = _resolve_json_path(chunk, match_expr[2:])
        if isinstance(val, (list, dict)):
            return bool(val)
        return val is not None and val != ""
    return False


def _eval_predicate(chunk: dict[str, Any], expr: str) -> bool:
    parts = [p.strip() for p in expr.split("&&")]
    for part in parts:
        m = re.match(r"^\$\.(.+?)\s*==\s*'([^']*)'$", part)
        if not m:
            return False
        path, expected = m.group(1), m.group(2)
        actual = _resolve_json_path(chunk, path)
        if str(actual) != expected:
            return False
    return True


def _resolve_json_path(obj: Any, path: str) -> Any:
    """Minimal JSONPath resolver for event_map match expressions."""
    tokens = re.findall(r"[^.\[\]]+|\[\d+\]", path)
    cur: Any = obj
    for token in tokens:
        if cur is None:
            return None
        if token.startswith("[") and token.endswith("]"):
            idx = int(token[1:-1])
            if not isinstance(cur, list) or idx >= len(cur):
                return None
            cur = cur[idx]
        else:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(token)
    return cur
