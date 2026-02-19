# ai-protocol-mock

AI-Protocol 运行时的统一 mock 服务。为 ai-lib-python、ai-lib-rust 等运行时提供 HTTP Provider Mock（OpenAI 及 Anthropic 格式）和 MCP JSON-RPC Mock。

## 功能

- **Manifest 驱动 HTTP Mock**：根据 provider manifest 生成 OpenAI 或 Anthropic 格式响应
- **STT / TTS / Rerank Mock**：模拟语音转写、语音合成、文档重排序端点（符合 OpenAI/Cohere 规范）
- **MCP JSON-RPC Mock**：实现 tools/list、tools/call、capabilities、initialize
- **可配置**：通过环境变量配置响应延迟、错误率、mock 内容
- **Docker**：`docker-compose up` 一键启动

## 快速开始

```bash
pip install -e .
python scripts/sync_manifests.py --force  # 从 ai-protocol 同步 manifest
uvicorn ai_protocol_mock.main:app --host 0.0.0.0 --port 4010
```

或使用 Docker：

```bash
docker-compose up -d
```

## 配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| HTTP_PORT | 4010 | HTTP 与 MCP 端口（MCP 路径为 /mcp） |
| MANIFEST_DIR | manifests | 同步 manifest 的目录 |
| MANIFEST_SYNC_URL | https://raw.githubusercontent.com/.../main/ | manifest 同步源 |
| RESPONSE_DELAY | 0 | 响应前延迟（秒） |
| ERROR_RATE | 0 | 返回 429/500/503 的概率 (0-1) |
| MOCK_CONTENT | Mock response... | 默认响应内容 |

### 测试控制头（X-Mock-*）

集成测试可通过请求头控制 mock 行为：

| 头 | 说明 | 示例 |
|----|------|------|
| X-Mock-Status | 强制返回指定 HTTP 错误状态 (400-599) | 429, 500, 503 |
| X-Mock-Content | 覆盖本次响应的文本内容 | 自定义文本 |
| X-Mock-Tool-Calls | 返回 tool_calls 而非文本 | 1, true, yes |

## 端点

- `POST /v1/chat/completions` - OpenAI 格式 chat
- `POST /v1/messages` - Anthropic 格式 chat
- `POST /v1/audio/transcriptions` - STT（OpenAI Whisper 格式），返回 `{"text": "..."}`
- `POST /v1/audio/speech` - TTS（OpenAI 格式），返回 `audio/mpeg` 字节流
- `POST /v2/rerank` - Rerank（Cohere v2 格式），请求 `{query, documents, top_n}`，返回 `{results, id, meta}`
- `POST /mcp` - MCP JSON-RPC（tools/list、tools/call、capabilities、initialize）
- `GET /health` - 健康检查
- `GET /status` - 状态及 manifest 同步信息
- `GET /providers` - 从 manifest 获取 provider 合约（provider_id、api_style、chat_path）

## 与 ai-lib-python 配合使用

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

或使用 mock 运行测试：

```bash
MOCK_HTTP_URL=http://localhost:4010 MOCK_MCP_URL=http://localhost:4010/mcp pytest tests/ -v
```

**远程 / 代理环境**：若本机配置了 HTTP/HTTPS 代理，需设置 `NO_PROXY` 包含 mock 服务 IP，以便 Python 的 httpx 直连：

```bash
NO_PROXY=192.168.2.13,localhost,127.0.0.1 MOCK_HTTP_URL=http://192.168.2.13:4010 MOCK_MCP_URL=http://192.168.2.13:4010/mcp pytest tests/ -v
```

## 与 ai-lib-rust 配合使用

```bash
export MOCK_HTTP_URL=http://localhost:4010
cargo run --example basic_usage
```

或运行 mock 集成测试：

```bash
MOCK_HTTP_URL=http://localhost:4010 MOCK_MCP_URL=http://localhost:4010/mcp cargo test -- --ignored --nocapture
```

或在代码中：

```rust
let client = AiClientBuilder::new()
    .base_url_override("http://localhost:4010")
    .build("openai/gpt-4o")
    .await?;
```

## Manifest 同步

```bash
python scripts/sync_manifests.py [--force] [--url URL] [--tag REF]
```

- `--force` - 覆盖已有文件
- `--tag REF` - 固定到指定 ai-protocol 版本（如 v0.7.1、main）
- `--url URL` - 自定义同步源（默认：ai-protocol main）

启动服务前运行以更新 manifest。Docker Compose 会在启动时自动执行同步。GitHub Action 每日运行以验证同步脚本。

## 开发

```bash
pip install -e ".[dev]"
pytest tests/ -v
ruff check src tests scripts
```

## License

MIT OR Apache-2.0
