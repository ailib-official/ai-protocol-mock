# ai-protocol-mock v0.1.5 Release Notes

**Release Date**: 2026-02-19

## Summary

Test-oriented enhancements: X-Mock-* request headers for controllable responses, tool_calls support, and expanded tests for ai-lib-rust / ai-lib-python integration.

## What's New

### X-Mock-* Request Headers

| Header | Description | Example |
|--------|-------------|---------|
| X-Mock-Status | Force HTTP status code | 429, 500, 503 |
| X-Mock-Content | Override response content | arbitrary string |
| X-Mock-Tool-Calls | Return tool_calls instead of text | 1, true, yes |

Enables deterministic error handling and tool_calls tests without changing mock config.

### Tool Calls Support

- Chat endpoint returns OpenAI-format `tool_calls` when `X-Mock-Tool-Calls` header is set
- Supports ai-lib-python `test_tools.py` and similar integration tests

### Tests & Docs

- Extended `test_mock.py` for X-Mock-* and tool_calls scenarios
- README / README_CN updated with header documentation
- Sync script and config improvements

## Upgrade

```bash
pip install -U ai-protocol-mock
```
