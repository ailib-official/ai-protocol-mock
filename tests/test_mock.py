"""Tests for ai-protocol-mock."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure package is importable when run without install
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest
from httpx import ASGITransport, AsyncClient

from ai_protocol_mock.main import app

transport = ASGITransport(app=app)


@pytest.mark.asyncio
async def test_health():
    """Test health endpoint."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_status():
    """Test status endpoint returns manifest sync metadata."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/status")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "manifest_sync" in data
    assert "version" in data


@pytest.mark.asyncio
async def test_providers():
    """Test providers endpoint returns provider contracts."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/providers")
    assert r.status_code == 200
    data = r.json()
    assert "providers" in data
    providers = data["providers"]
    assert len(providers) >= 1
    for p in providers:
        assert "provider_id" in p
        assert "api_style" in p
        assert "chat_path" in p


@pytest.mark.asyncio
async def test_http_mock_openai():
    """Test HTTP mock returns OpenAI-format response."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hi"}]},
        )
    assert r.status_code == 200
    data = r.json()
    assert "choices" in data
    assert len(data["choices"]) > 0
    assert data["choices"][0]["message"]["content"]


@pytest.mark.asyncio
async def test_http_mock_openai_streaming():
    """Test HTTP mock returns OpenAI-format streaming response."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hi"}], "stream": True},
        )
    assert r.status_code == 200
    assert "text/event-stream" in r.headers.get("content-type", "")
    text = r.text
    assert "data: " in text
    assert "[DONE]" in text


@pytest.mark.asyncio
async def test_http_mock_anthropic():
    """Test HTTP mock returns Anthropic-format response."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/v1/messages",
            json={"model": "claude-3-5-sonnet", "messages": [{"role": "user", "content": "Hi"}]},
        )
    assert r.status_code == 200
    data = r.json()
    assert "content" in data
    assert data["content"][0]["text"]
    assert "usage" in data
    assert "input_tokens" in data["usage"]


@pytest.mark.asyncio
async def test_mcp_tools_list():
    """Test MCP tools/list returns tool list."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
    assert r.status_code == 200
    data = r.json()
    assert "result" in data
    assert "tools" in data["result"]
    assert len(data["result"]["tools"]) > 0


@pytest.mark.asyncio
async def test_mcp_tools_call():
    """Test MCP tools/call returns result."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "read_file", "arguments": {"path": "/tmp/test.txt"}},
            },
        )
    assert r.status_code == 200
    data = r.json()
    assert "result" in data
    assert "content" in data["result"]
    assert data["result"]["content"][0]["type"] == "text"


@pytest.mark.asyncio
async def test_mcp_initialize():
    """Test MCP initialize returns server info."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}},
        )
    assert r.status_code == 200
    data = r.json()
    assert "result" in data
    assert "serverInfo" in data["result"]
