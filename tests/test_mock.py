"""Tests for ai-protocol-mock."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure package is importable when run without install
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest
from httpx import ASGITransport, AsyncClient

from ai_protocol_mock.main import app
from ai_protocol_mock.mocks.http_provider import get_provider_contracts

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
    provider_ids = {p.get("provider_id") for p in providers}
    for expected in ("cohere", "moonshot", "zhipu", "jina"):
        assert expected in provider_ids
    for p in providers:
        assert "provider_id" in p
        assert "api_style" in p
        assert "chat_path" in p
        assert "has_capability_profile" in p
        assert "capability_profile_phase" in p
        assert "has_ios_dimensions" in p

    assert isinstance(next(iter(providers)), dict)


def test_provider_contracts_capability_profile_summary(tmp_path: Path):
    """Contracts should expose capability_profile summary when present."""
    providers_dir = tmp_path / "v2" / "providers"
    providers_dir.mkdir(parents=True, exist_ok=True)
    (providers_dir / "openai.yaml").write_text(
        """
id: openai
name: OpenAI
endpoint:
  base_url: "https://api.openai.com/v1"
  chat: "/chat/completions"
streaming:
  decoder:
    strategy: openai_chat
capability_profile:
  phase: "ios_v1"
  inputs:
    modalities: ["text"]
  outcomes:
    types: ["text_completion"]
  systems:
    requires: ["search"]
        """.strip(),
        encoding="utf-8",
    )
    contracts = get_provider_contracts(tmp_path)
    openai = next((item for item in contracts if item.get("provider_id") == "openai"), None)
    assert openai is not None
    assert openai["has_capability_profile"] is True
    assert openai["capability_profile_phase"] == "ios_v1"
    assert openai["has_ios_dimensions"] is True


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
async def test_http_mock_gemini_generate_content():
    """Test Gemini-style generateContent endpoint."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/v1beta/models/gemini-2.0-flash:generateContent",
            json={"contents": [{"role": "user", "parts": [{"text": "Hi"}]}]},
        )
    assert r.status_code == 200
    data = r.json()
    assert "candidates" in data
    assert data["candidates"][0]["content"]["parts"][0]["text"]
    assert "usageMetadata" in data


@pytest.mark.asyncio
async def test_http_mock_gemini_stream_generate_content():
    """Test Gemini-style streamGenerateContent endpoint."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/v1beta/models/gemini-2.0-flash:streamGenerateContent",
            json={"contents": [{"role": "user", "parts": [{"text": "Hi"}]}], "stream": True},
        )
    assert r.status_code == 200
    assert "text/event-stream" in r.headers.get("content-type", "")
    assert "data: " in r.text
    assert "[DONE]" in r.text


@pytest.mark.asyncio
async def test_http_mock_accepts_tool_messages():
    """Test mock accepts tool role (AI-Protocol standard_message_roles)."""
    messages = [
        {"role": "user", "content": "Weather in Tokyo?"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_abc123",
                    "type": "function",
                    "function": {"name": "get_weather", "arguments": '{"city":"Tokyo"}'},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_abc123", "content": "Sunny, 22°C"},
    ]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4o",
                "messages": messages,
                "tools": [{"type": "function", "function": {"name": "get_weather"}}],
            },
        )
    assert r.status_code == 200
    data = r.json()
    assert "choices" in data
    assert len(data["choices"]) > 0


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


@pytest.mark.asyncio
async def test_stt_transcriptions():
    """Test STT mock returns OpenAI Whisper format."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/v1/audio/transcriptions",
            files={"file": ("audio.wav", b"\x00" * 100, "audio/wav")},
            data={"model": "whisper-1"},
        )
    assert r.status_code == 200
    data = r.json()
    assert "text" in data
    assert "mock transcription" in data["text"]


@pytest.mark.asyncio
async def test_tts_speech():
    """Test TTS mock returns audio bytes."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/v1/audio/speech",
            json={"model": "tts-1", "input": "Hello", "voice": "alloy"},
        )
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("audio/")
    assert len(r.content) > 0


@pytest.mark.asyncio
async def test_rerank():
    """Test Rerank mock returns Cohere v2 format."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/v2/rerank",
            json={
                "model": "rerank-v3.5",
                "query": "test query",
                "documents": ["doc1", "doc2", "doc3"],
                "top_n": 2,
            },
        )
    assert r.status_code == 200
    data = r.json()
    assert "results" in data
    assert len(data["results"]) == 2
    for item in data["results"]:
        assert "index" in item
        assert "relevance_score" in item


@pytest.mark.asyncio
async def test_video_generation_async_polling_flow():
    """Test async video generation and polling lifecycle."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post(
            "/v1/video/generations",
            json={"model": "video-gen-1", "prompt": "A city skyline at sunset", "async": True},
        )
        assert create_resp.status_code == 202
        created = create_resp.json()
        assert created["status"] == "queued"
        job_id = created["id"]

        poll_1 = await client.get(f"/v1/video/generations/{job_id}")
        assert poll_1.status_code == 200
        assert poll_1.json()["status"] in {"running", "queued"}

        poll_2 = await client.get(f"/v1/video/generations/{job_id}")
        assert poll_2.status_code == 200
        data = poll_2.json()
        assert data["status"] == "succeeded"
        assert "output" in data
        assert data["output"]["content_type"] == "video/mp4"


@pytest.mark.asyncio
async def test_video_generation_sync_mode():
    """Test sync video generation response path."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/v1/video/generations",
            json={"model": "video-gen-1", "prompt": "A robot walking", "async": False},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "succeeded"
    assert data["output"]["content_type"] == "video/mp4"


@pytest.mark.asyncio
async def test_video_generation_not_found():
    """Polling an unknown video job should return 404."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/v1/video/generations/job_missing")
    assert r.status_code == 404
    assert "error" in r.json()


@pytest.mark.asyncio
async def test_video_generation_async_failed_terminal_state():
    """Test async video generation can end in failed terminal state."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post(
            "/v1/video/generations",
            json={"model": "video-gen-1", "prompt": "Fail case", "async": True},
            headers={"X-Mock-Video-Terminal": "failed"},
        )
        assert create_resp.status_code == 202
        job_id = create_resp.json()["id"]

        await client.get(f"/v1/video/generations/{job_id}")  # queued/running
        poll_terminal = await client.get(f"/v1/video/generations/{job_id}")
        assert poll_terminal.status_code == 200
        payload = poll_terminal.json()
        assert payload["status"] == "failed"
        assert payload["terminal_state"] == "failed"
        assert "error" in payload
        assert payload["error"]["code"] == "video_generation_failed"

        # terminal should remain stable on subsequent polls
        poll_again = await client.get(f"/v1/video/generations/{job_id}")
        assert poll_again.status_code == 200
        assert poll_again.json()["status"] == "failed"


@pytest.mark.asyncio
async def test_video_generation_async_cancelled_terminal_state():
    """Test async video generation can end in cancelled terminal state."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post(
            "/v1/video/generations",
            json={"model": "video-gen-1", "prompt": "Cancel case", "async": True, "terminal_state": "cancelled"},
        )
        assert create_resp.status_code == 202
        job_id = create_resp.json()["id"]

        await client.get(f"/v1/video/generations/{job_id}")  # queued/running
        poll_terminal = await client.get(f"/v1/video/generations/{job_id}")
        assert poll_terminal.status_code == 200
        payload = poll_terminal.json()
        assert payload["status"] == "cancelled"
        assert payload["terminal_state"] == "cancelled"
        assert "cancellation" in payload
        assert payload["cancellation"]["reason"] == "mock_cancelled_for_test"


# --- Test control headers (X-Mock-*) for integration tests ---


@pytest.mark.asyncio
async def test_x_mock_status():
    """Test X-Mock-Status header forces error response."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for status in (429, 500, 503):
            r = await client.post(
                "/v1/chat/completions",
                json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hi"}]},
                headers={"X-Mock-Status": str(status)},
            )
            assert r.status_code == status
            data = r.json()
            assert "error" in data


@pytest.mark.asyncio
async def test_x_mock_content():
    """Test X-Mock-Content header overrides response content."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hi"}]},
            headers={"X-Mock-Content": "Custom response from test"},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["choices"][0]["message"]["content"] == "Custom response from test"


@pytest.mark.asyncio
async def test_x_mock_tool_calls():
    """Test X-Mock-Tool-Calls header returns tool_calls response."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Weather in Tokyo?"}]},
            headers={"X-Mock-Tool-Calls": "1"},
        )
    assert r.status_code == 200
    data = r.json()
    assert "choices" in data
    msg = data["choices"][0]["message"]
    assert "tool_calls" in msg
    assert len(msg["tool_calls"]) > 0
    assert msg["tool_calls"][0]["function"]["name"] == "get_weather"


@pytest.mark.asyncio
async def test_x_mock_invalid_content_type():
    """Test invalid content type injection for failure simulation."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/v1/video/generations",
            json={"model": "video-gen-1", "async": True},
            headers={"X-Mock-Invalid-Content-Type": "1"},
        )
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("text/plain")
