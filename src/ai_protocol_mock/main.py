"""Main FastAPI application for ai-protocol-mock.

ai-protocol-mock 主应用模块：FastAPI 入口，挂载 HTTP 与 MCP 路由。
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from ai_protocol_mock import __version__
from ai_protocol_mock.config import config
from ai_protocol_mock.mocks.http_provider import create_http_router, get_provider_contracts
from ai_protocol_mock.mocks.mcp_server import create_mcp_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure manifest dir exists on startup."""
    config.MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="ai-protocol-mock",
        description="Unified mock server for AI-Protocol runtimes",
        version=__version__,
        lifespan=lifespan,
    )
    app.include_router(create_http_router())
    app.include_router(create_mcp_router())

    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {"status": "ok", "service": "ai-protocol-mock"}

    @app.get("/status")
    async def status():
        """Status with manifest sync info and version check.
        Returns sync metadata; if manifest is stale (synced_from outdated),
        consider re-running sync-manifests.py.
        """
        import json

        meta_file = config.MANIFEST_DIR / "_sync_meta.json"
        meta = {}
        if meta_file.exists():
            meta = json.loads(meta_file.read_text())
        return {"status": "ok", "manifest_sync": meta, "version": __version__}

    @app.get("/providers")
    async def providers():
        """Return provider contracts from manifests.
        Each contract includes provider_id, api_style, chat_path for runtime compatibility.
        """
        return {"providers": get_provider_contracts()}

    return app


app = create_app()
