"""Tests for ai-protocol-mock."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure package is importable when run without install
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest
from httpx import AsyncClient

from ai_protocol_mock.main import app


@pytest.mark.asyncio
async def test_health():
    """Test health endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_http_mock_openai():
    """Test HTTP mock returns OpenAI-format response."""
    async with AsyncClient(app=app, base_url="http://test") as client:
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
async def test_http_mock_anthropic():
    """Test HTTP mock returns Anthropic-format response."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        r = await client.post(
            "/v1/messages",
            json={"model": "claude-3-5-sonnet", "messages": [{"role": "user", "content": "Hi"}]},
        )
    assert r.status_code == 200
    data = r.json()
    assert "content" in data
    assert data["content"][0]["text"]


@pytest.mark.asyncio
async def test_mcp_tools_list():
    """Test MCP tools/list returns tool list."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        r = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
    assert r.status_code == 200
    data = r.json()
    assert "result" in data
    assert "tools" in data["result"]
    assert len(data["result"]["tools"]) > 0
