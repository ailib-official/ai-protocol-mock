# ai-protocol-mock

Unified mock server for AI-Protocol runtimes. Provides HTTP provider mock (OpenAI and Anthropic formats) and MCP JSON-RPC mock for testing ai-lib-python, ai-lib-rust, and other runtimes.

## Features

- **Manifest-driven HTTP mock**: Generates responses in OpenAI or Anthropic format based on provider manifests
- **STT / TTS / Rerank mock**: Simulates speech-to-text, text-to-speech, and document reranking endpoints (OpenAI/Cohere compliant)
- **MCP JSON-RPC mock**: Implements `tools/list`, `tools/call`, `capabilities`, `initialize`
- **Configurable**: Response delay, error rate, mock content via environment variables
- **Docker**: One-command startup with `docker-compose up`

## Quick Start

```bash
# Install and run
pip install -e .
python scripts/sync_manifests.py --force  # Sync manifests from ai-protocol
uvicorn ai_protocol_mock.main:app --host 0.0.0.0 --port 4010
```

Or with Docker:

```bash
docker-compose up -d
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| HTTP_PORT | 4010 | Port for HTTP and MCP (MCP at /mcp) |
| MANIFEST_DIR | manifests | Directory for synced manifests |
| MANIFEST_SYNC_URL | https://raw.githubusercontent.com/hiddenpath/ai-protocol/main/ | Source for manifest sync |
| RESPONSE_DELAY | 0 | Delay in seconds before responding |
| ERROR_RATE | 0 | Probability (0-1) of returning 429/500/503 |
| MOCK_CONTENT | Mock response from ai-protocol-mock | Default response content |

### Test Control Headers (X-Mock-*)

For integration tests, requests can include these headers to control mock behavior:

| Header | Description | Example |
|--------|-------------|---------|
| X-Mock-Status | Force HTTP error status (400-599) | 429, 500, 503 |
| X-Mock-Content | Override response content for this request | Custom text |
| X-Mock-Tool-Calls | Return tool_calls instead of text | 1, true, yes |
| X-Mock-Invalid-Content-Type | Inject `text/plain` payload for robustness tests | 1 |
| X-Mock-Video-Terminal | Force async video terminal state (`succeeded`/`failed`/`cancelled`) | failed |

## Endpoints

- `POST /v1/chat/completions` - OpenAI-format chat
- `POST /v1/messages` - Anthropic-format chat
- `POST /v1/audio/transcriptions` - STT (OpenAI Whisper format), returns `{"text": "..."}`
- `POST /v1/audio/speech` - TTS (OpenAI format), returns `audio/mpeg` bytes
- `POST /v2/rerank` - Rerank (Cohere v2 format), request `{query, documents, top_n}`, returns `{results, id, meta}`
- `POST /v1/video/generations` - Video generation (sync + async polling)
- `GET /v1/video/generations/{job_id}` - Poll async video generation status
- `POST /mcp` - MCP JSON-RPC (`tools/list`, `tools/call`, `capabilities`, `initialize`)
- `GET /health` - Health check
- `GET /status` - Status with manifest sync metadata
- `GET /providers` - Provider contracts from manifests (provider_id, api_style, chat_path)

### Video Generation Lifecycle

Async video generation jobs follow a deterministic state machine:

`queued -> running -> terminal`

Terminal states:

- `succeeded` (default): returns `output` with mock mp4 metadata
- `failed`: returns `error` payload (`video_generation_failed`)
- `cancelled`: returns `cancellation` payload (`mock_cancelled_for_test`)

Controls:

- request body `terminal_state` or header `X-Mock-Video-Terminal`
- unknown values fall back to `succeeded`

## Using with ai-lib-python

```python
import os
os.environ["MOCK_HTTP_URL"] = "http://localhost:4010"

from ai_lib_python.client import AiClient
from ai_lib_python.types.message import Message

client = await AiClient.create(
    "openai/gpt-4o",
    api_key="sk-test",
    base_url="http://localhost:4010"
)
response = await client.chat().messages([Message.user("Hi")]).execute()
print(response.content)
```

Or run tests with mock:

```bash
MOCK_HTTP_URL=http://localhost:4010 MOCK_MCP_URL=http://localhost:4010/mcp pytest tests/ -v
```

## Third-Party Integration (ZeroClaw, etc.)

ai-protocol-mock is designed for downstream runtimes and frameworks that need deterministic testing without real API calls:

- **ZeroClaw / ZeroSpider**: Set `MOCK_HTTP_URL` and `MOCK_MCP_URL` to the mock server (e.g. `http://192.168.2.13:4010`) before running integration tests. Use `NO_PROXY` to bypass HTTP proxies when testing against a local or LAN mock.
- **CI pipelines**: Start mock via `docker-compose up -d` or `uvicorn ai_protocol_mock.main:app --host 0.0.0.0 --port 4010`, then run tests with the env vars above.
- **Error injection**: Set `ERROR_RATE=0.1` to simulate 429/500/503 for resilience testing.

**Remote / proxy environments**: If your machine uses HTTP/HTTPS proxy, set `NO_PROXY` to include the mock server IP so Python's httpx can reach it directly:

```bash
NO_PROXY=192.168.2.13,localhost,127.0.0.1 MOCK_HTTP_URL=http://192.168.2.13:4010 MOCK_MCP_URL=http://192.168.2.13:4010/mcp pytest tests/ -v
```

## Using with ai-lib-rust

```bash
export MOCK_HTTP_URL=http://localhost:4010
cargo run --example basic_usage
```

Or run mock integration tests:

```bash
MOCK_HTTP_URL=http://localhost:4010 MOCK_MCP_URL=http://localhost:4010/mcp cargo test -- --ignored --nocapture
```

Or in code:

```rust
let client = AiClientBuilder::new()
    .base_url_override("http://localhost:4010")
    .build("openai/gpt-4o")
    .await?;
```

## Manifest Sync

Sync manifests from the ai-protocol repository:

```bash
python scripts/sync_manifests.py [--force] [--url URL] [--tag REF]
```

- `--force` - Overwrite existing files
- `--tag REF` - Pin to a specific ai-protocol ref (e.g. `v0.7.1`, `main`)
- `--url URL` - Custom base URL (default: ai-protocol main)

Run before starting the server to ensure manifests are up to date. Docker Compose runs sync automatically on startup. A GitHub Action runs sync daily to validate the script.

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v
ruff check src tests scripts
```

## License

MIT OR Apache-2.0
