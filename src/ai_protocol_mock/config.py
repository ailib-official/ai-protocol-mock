"""Configuration loading for ai-protocol-mock.

配置加载模块：从环境变量读取 mock 服务配置（端口、manifest 路径等）。
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Mock server configuration from environment variables."""

    HTTP_PORT: int = int(os.getenv("HTTP_PORT", "4010"))
    MCP_PORT: int = int(os.getenv("MCP_PORT", "4011"))
    MANIFEST_DIR: Path = Path(os.getenv("MANIFEST_DIR", "manifests"))
    MANIFEST_SYNC_URL: str = os.getenv(
        "MANIFEST_SYNC_URL",
        "https://raw.githubusercontent.com/ailib-official/ai-protocol/749cb825c99f03e9dc737294b41fd5f5552533b4/",
    )
    RESPONSE_DELAY: float = float(os.getenv("RESPONSE_DELAY", "0.0"))
    ERROR_RATE: float = float(os.getenv("ERROR_RATE", "0.0"))
    MOCK_CONTENT: str = os.getenv("MOCK_CONTENT", "Mock response from ai-protocol-mock")


config = Config()
