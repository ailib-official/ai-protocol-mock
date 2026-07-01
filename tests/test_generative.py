"""Tests for generative LLM mock scenarios (Wave-4 PT-059).

生成式大模型 Mock 场景测试：token usage、reasoning、structured output、
parallel/recursive tool calls、error injection。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest
from httpx import ASGITransport, AsyncClient

from ai_protocol_mock.main import app

transport = ASGITransport(app=app)
BASE = "http://test"


@pytest.mark.asyncio
async def test_context_overflow_error():
    async with AsyncClient(transport=transport, base_url=BASE) as client:
        r = await client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]},
            headers={"X-Mock-Error": "context_overflow"},
        )
    assert r.status_code == 400
    err = r.json()["error"]
    assert err["code"] == "context_length_exceeded"
    assert err["type"] == "invalid_request_error"
    assert "128000" in err["message"]


@pytest.mark.asyncio
async def test_content_filter_error():
    async with AsyncClient(transport=transport, base_url=BASE) as client:
        r = await client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "bad"}]},
            headers={"X-Mock-Error": "content_filter"},
        )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "content_filter"


@pytest.mark.asyncio
async def test_rate_limit_error_with_retry_after():
    async with AsyncClient(transport=transport, base_url=BASE) as client:
        r = await client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o", "messages": []},
            headers={"X-Mock-Error": "rate_limit"},
        )
    assert r.status_code == 429
    assert r.headers.get("retry-after") == "5"
    assert r.json()["error"]["code"] == "rate_limit_exceeded"


@pytest.mark.asyncio
async def test_openai_reasoning_sync():
    async with AsyncClient(transport=transport, base_url=BASE) as client:
        r = await client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "think"}]},
            headers={"X-Mock-Reasoning": "true"},
        )
    assert r.status_code == 200
    data = r.json()
    msg = data["choices"][0]["message"]
    assert "reasoning_content" in msg
    assert msg["reasoning_content"]
    assert msg["content"]
    usage = data["usage"]
    assert "completion_tokens_details" in usage
    assert usage["completion_tokens_details"]["reasoning_tokens"] > 0


@pytest.mark.asyncio
async def test_openai_reasoning_stream():
    async with AsyncClient(transport=transport, base_url=BASE) as client:
        r = await client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o", "messages": [], "stream": True},
            headers={"X-Mock-Reasoning": "true"},
        )
    assert r.status_code == 200
    lines = r.text.strip().split("\n")
    data_lines = [line for line in lines if line.startswith("data: ") and line != "data: [DONE]"]
    has_reasoning = any('"reasoning_content"' in line for line in data_lines)
    has_content = any('"content"' in line for line in data_lines)
    assert has_reasoning
    assert has_content


@pytest.mark.asyncio
async def test_anthropic_reasoning_sync():
    async with AsyncClient(transport=transport, base_url=BASE) as client:
        r = await client.post(
            "/v1/messages",
            json={"model": "claude-3.5-sonnet", "messages": [{"role": "user", "content": "think"}]},
            headers={"X-Mock-Reasoning": "true"},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["content"][0]["type"] == "thinking"
    assert data["content"][1]["type"] == "text"


@pytest.mark.asyncio
async def test_anthropic_reasoning_stream():
    async with AsyncClient(transport=transport, base_url=BASE) as client:
        r = await client.post(
            "/v1/messages",
            json={"model": "claude-3.5-sonnet", "messages": [], "stream": True},
            headers={"X-Mock-Reasoning": "true"},
        )
    assert r.status_code == 200
    text = r.text
    assert "thinking_delta" in text
    assert "text_delta" in text


@pytest.mark.asyncio
async def test_structured_output_json_object():
    async with AsyncClient(transport=transport, base_url=BASE) as client:
        r = await client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": "list colors"}],
                "response_format": {"type": "json_object"},
            },
        )
    assert r.status_code == 200
    data = r.json()
    content = json.loads(data["choices"][0]["message"]["content"])
    assert "result" in content
    assert content["result"] == "mock_structured_output"


@pytest.mark.asyncio
async def test_structured_output_json_schema():
    async with AsyncClient(transport=transport, base_url=BASE) as client:
        r = await client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4o",
                "messages": [],
                "response_format": {"type": "json_schema", "json_schema": {"name": "test"}},
            },
        )
    assert r.status_code == 200
    content = json.loads(r.json()["choices"][0]["message"]["content"])
    assert "count" in content


@pytest.mark.asyncio
async def test_parallel_tool_calls_sync():
    async with AsyncClient(transport=transport, base_url=BASE) as client:
        r = await client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o", "messages": []},
            headers={"X-Mock-Tool-Calls": "parallel"},
        )
    assert r.status_code == 200
    tools = r.json()["choices"][0]["message"]["tool_calls"]
    assert len(tools) == 2
    assert tools[0]["function"]["name"] == "get_weather"
    assert tools[1]["function"]["name"] == "get_time"


@pytest.mark.asyncio
async def test_parallel_tool_calls_stream():
    async with AsyncClient(transport=transport, base_url=BASE) as client:
        r = await client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o", "messages": [], "stream": True},
            headers={"X-Mock-Tool-Calls": "parallel"},
        )
    assert r.status_code == 200
    text = r.text
    assert "call_mock_1" in text
    assert "call_mock_2" in text
    assert "get_weather" in text
    assert "get_time" in text


@pytest.mark.asyncio
async def test_recursive_tool_calls():
    async with AsyncClient(transport=transport, base_url=BASE) as client:
        r1 = await client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "start"}]},
            headers={"X-Mock-Tool-Calls": "recursive", "X-Mock-Tool-Depth": "2"},
        )
    assert r1.status_code == 200
    data1 = r1.json()
    assert data1["choices"][0].get("finish_reason") == "tool_calls"
    assert data1["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "step_1_tool"

    async with AsyncClient(transport=transport, base_url=BASE) as client:
        r2 = await client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4o",
                "messages": [
                    {"role": "user", "content": "start"},
                    {"role": "tool", "tool_call_id": "x", "content": "result1"},
                    {"role": "tool", "tool_call_id": "y", "content": "result2"},
                ],
            },
            headers={"X-Mock-Tool-Calls": "recursive", "X-Mock-Tool-Depth": "2"},
        )
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["choices"][0]["message"]["content"]


@pytest.mark.asyncio
async def test_openai_usage_with_reasoning_tokens():
    async with AsyncClient(transport=transport, base_url=BASE) as client:
        r = await client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]},
            headers={"X-Mock-Usage-Format": "openai"},
        )
    assert r.status_code == 200
    usage = r.json()["usage"]
    assert "prompt_tokens" in usage
    assert "completion_tokens" in usage
    assert "total_tokens" in usage
    assert "completion_tokens_details" in usage


@pytest.mark.asyncio
async def test_anthropic_usage_with_cache():
    async with AsyncClient(transport=transport, base_url=BASE) as client:
        r = await client.post(
            "/v1/messages",
            json={"model": "claude-3.5-sonnet", "messages": [{"role": "user", "content": "hi"}]},
            headers={"X-Mock-Usage-Format": "anthropic"},
        )
    assert r.status_code == 200
    usage = r.json()["usage"]
    assert "input_tokens" in usage
    assert "output_tokens" in usage
    assert "cache_creation_input_tokens" in usage
    assert "cache_read_input_tokens" in usage


@pytest.mark.asyncio
async def test_stream_interrupt():
    async with AsyncClient(transport=transport, base_url=BASE) as client:
        r = await client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o", "messages": [], "stream": True},
            headers={"X-Mock-Error": "stream_interrupt"},
        )
    assert r.status_code == 200
    lines = [line for line in r.text.strip().split("\n") if line.startswith("data: ")]
    assert len(lines) <= 4
    assert "data: [DONE]" not in r.text
