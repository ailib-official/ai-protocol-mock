"""Load provider manifests from synced ai-protocol tree.

从已同步的 ai-protocol 目录树加载 provider manifest（v1/v2）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_PROVIDER_DIRS = ("v1/providers", "v2/providers", "providers")


class ManifestRegistry:
    """In-memory index of provider manifests keyed by provider id."""

    def __init__(self, manifest_dir: Path) -> None:
        self._manifest_dir = manifest_dir
        self._manifests: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        manifests: dict[str, dict[str, Any]] = {}
        for rel in _PROVIDER_DIRS:
            providers_dir = self._manifest_dir / rel
            if not providers_dir.is_dir():
                continue
            for path in sorted(providers_dir.glob("*.yaml")):
                try:
                    data = yaml.safe_load(path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if not isinstance(data, dict):
                    continue
                pid = data.get("id", path.stem)
                if isinstance(pid, str) and pid:
                    manifests[pid] = data
        self._manifests = manifests

    def provider_ids(self) -> set[str]:
        return set(self._manifests)

    def get(self, provider_id: str) -> dict[str, Any] | None:
        return self._manifests.get(provider_id)

    def require(self, provider_id: str) -> dict[str, Any]:
        manifest = self.get(provider_id)
        if manifest is None:
            raise KeyError(provider_id)
        return manifest

    def items(self) -> list[tuple[str, dict[str, Any]]]:
        return sorted(self._manifests.items(), key=lambda item: item[0])

    @staticmethod
    def endpoint_dict(manifest: dict[str, Any]) -> dict[str, Any]:
        ep = manifest.get("endpoints") or manifest.get("endpoint") or {}
        return ep if isinstance(ep, dict) else {}

    @staticmethod
    def has_chat_endpoint(manifest: dict[str, Any]) -> bool:
        ep = ManifestRegistry.endpoint_dict(manifest)
        chat = ep.get("chat")
        if isinstance(chat, dict):
            return bool(chat.get("path"))
        return isinstance(chat, str) and bool(chat)

    @staticmethod
    def rerank_path(manifest: dict[str, Any]) -> str | None:
        ep = ManifestRegistry.endpoint_dict(manifest)
        rerank = ep.get("rerank")
        if isinstance(rerank, str) and rerank:
            return rerank if rerank.startswith("/") else f"/{rerank}"
        return None

    @staticmethod
    def is_rerank_only(manifest: dict[str, Any]) -> bool:
        """True when manifest exposes rerank without a chat endpoint."""
        rerank = ManifestRegistry.rerank_path(manifest)
        if not rerank:
            return False
        if ManifestRegistry.has_chat_endpoint(manifest):
            return False
        caps = manifest.get("capabilities")
        if isinstance(caps, dict):
            required = caps.get("required")
            if isinstance(required, list) and "rerank" in required:
                return True
        return not ManifestRegistry.has_chat_endpoint(manifest)

    @staticmethod
    def primary_path(manifest: dict[str, Any]) -> str:
        """Primary wire path: chat when present, else rerank, else default."""
        if ManifestRegistry.has_chat_endpoint(manifest):
            return ManifestRegistry.chat_path(manifest)
        rerank = ManifestRegistry.rerank_path(manifest)
        if rerank:
            return rerank
        return "/chat/completions"

    @staticmethod
    def chat_path(manifest: dict[str, Any]) -> str:
        """Extract chat endpoint path from manifest (v1 or v2 endpoint shape)."""
        ep = manifest.get("endpoints") or manifest.get("endpoint") or {}
        if not isinstance(ep, dict):
            return "/chat/completions"
        chat = ep.get("chat")
        if isinstance(chat, dict):
            return chat.get("path", "/chat/completions") or "/chat/completions"
        if isinstance(chat, str) and chat:
            return chat if chat.startswith("/") else f"/{chat}"
        return "/chat/completions"

    @staticmethod
    def decoder_strategy(manifest: dict[str, Any]) -> str | None:
        streaming = manifest.get("streaming")
        if not isinstance(streaming, dict):
            return None
        decoder = streaming.get("decoder")
        if not isinstance(decoder, dict):
            return None
        strategy = decoder.get("strategy")
        return strategy if isinstance(strategy, str) else None

    @staticmethod
    def event_map(manifest: dict[str, Any]) -> list[dict[str, Any]] | None:
        streaming = manifest.get("streaming")
        if not isinstance(streaming, dict):
            return None
        event_map = streaming.get("event_map")
        if not isinstance(event_map, list):
            return None
        return [e for e in event_map if isinstance(e, dict)]
