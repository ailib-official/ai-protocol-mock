# ai-protocol-mock

AI-Protocol 运行时的统一 mock 服务。为 ai-lib-python、ai-lib-rust 等运行时提供 HTTP Provider Mock（OpenAI 及 Anthropic 格式）和 MCP JSON-RPC Mock。

## 功能

- **Manifest 驱动 HTTP Mock**：根据 provider manifest 生成 OpenAI 或 Anthropic 格式响应
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
| MANIFEST_SYNC_URL | ai-protocol main | manifest 同步源 |
| RESPONSE_DELAY | 0 | 响应前延迟（秒） |
| ERROR_RATE | 0 | 返回 429/500/503 的概率 (0-1) |
| MOCK_CONTENT | Mock response... | 默认响应内容 |

## 端点

- `POST /v1/chat/completions` - OpenAI 格式 chat
- `POST /v1/messages` - Anthropic 格式 chat
- `POST /mcp` - MCP JSON-RPC（tools/list、tools/call、capabilities、initialize）
- `GET /health` - 健康检查
- `GET /status` - 状态及 manifest 同步信息
- `GET /providers` - 从 manifest 获取 provider 合约（provider_id、api_style、chat_path）

## 与 ai-lib-python 配合使用

```python
client = await AiClient.create(
    "openai/gpt-4o",
    api_key="sk-test",
    base_url="http://localhost:4010"
)
```

## 与 ai-lib-rust 配合使用

```bash
export MOCK_HTTP_URL=http://localhost:4010
cargo run --example basic_usage
```

## Manifest 同步

```bash
python scripts/sync_manifests.py [--force] [--url URL] [--tag REF]
```

- `--force` - 覆盖已有文件
- `--tag REF` - 固定到指定 ai-protocol 版本（如 v0.7.1、main）
- `--url URL` - 自定义同步源（默认：ai-protocol main）

启动服务前运行以更新 manifest。Docker Compose 会在启动时自动执行同步。GitHub Action 每日运行以验证同步脚本。

## License

MIT OR Apache-2.0
