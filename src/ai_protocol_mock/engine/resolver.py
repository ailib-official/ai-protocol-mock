"""Resolve provider wire profile from manifest + ProviderContract (MOCK-001-R1).

根据 manifest 与 ProviderContract 解析 provider 线路配置（MOCK-001-R1）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from ai_protocol_mock.registry.contracts import ContractRegistry
from ai_protocol_mock.registry.manifests import ManifestRegistry

# Manifest streaming.decoder.strategy → canonical api_style (ARCH-001: from manifest, not path).
_DECODER_STRATEGY_TO_API_STYLE: dict[str, str] = {
    "openai_chat": "openai_chat",
    "anthropic_event_stream": "anthropic_messages",
    "gemini_generate": "gemini_generate",
    "cohere_v2": "cohere_v2",
}

# Public summary api_style aliases for /providers compatibility.
_API_STYLE_PUBLIC_ALIASES: dict[str, str] = {
    "openai_chat": "openai_compatible",
}


@dataclass(frozen=True)
class ProviderResolution:
    """Resolved wire profile for a single provider."""

    provider_id: str
    name: str
    api_style: str
    chat_path: str
    source: Literal["contract", "manifest_decoder", "manifest_rerank"]
    contract: dict[str, Any] | None
    manifest: dict[str, Any]
    event_map: list[dict[str, Any]] | None
    streaming_done_signal: str | None

    def public_api_style(self) -> str:
        """api_style string exposed on /providers (backward compatible)."""
        return _API_STYLE_PUBLIC_ALIASES.get(self.api_style, self.api_style)

    def response_handler(self) -> str:
        """Internal mock response generator key (openai | anthropic | gemini)."""
        if self.api_style == "rerank":
            return "openai"
        if self.api_style == "anthropic_messages":
            return "anthropic"
        if self.api_style == "gemini_generate":
            return "gemini"
        return "openai"


class ContractResolver:
    """Combines ManifestRegistry + ContractRegistry to resolve provider wire metadata."""

    def __init__(self, manifest_dir: Path) -> None:
        self._manifest_dir = manifest_dir
        self._manifests = ManifestRegistry(manifest_dir)
        self._contracts = ContractRegistry(manifest_dir)

    @property
    def manifest_registry(self) -> ManifestRegistry:
        return self._manifests

    def resolve(self, provider_id: str) -> ProviderResolution:
        manifest = self._manifests.require(provider_id)
        contract = self._contracts.get_for_provider(provider_id)
        chat_path = ManifestRegistry.primary_path(manifest)
        event_map = ManifestRegistry.event_map(manifest)

        if contract and isinstance(contract.get("api_style"), str):
            api_style = contract["api_style"]
            source: Literal["contract", "manifest_decoder", "manifest_rerank"] = "contract"
        elif ManifestRegistry.is_rerank_only(manifest):
            api_style = "rerank"
            source = "manifest_rerank"
        else:
            strategy = ManifestRegistry.decoder_strategy(manifest)
            if not strategy or strategy not in _DECODER_STRATEGY_TO_API_STYLE:
                raise KeyError(
                    f"{provider_id}: missing ProviderContract and unknown streaming.decoder.strategy={strategy!r}"
                )
            api_style = _DECODER_STRATEGY_TO_API_STYLE[strategy]
            source = "manifest_decoder"

        streaming_done_signal = _streaming_done_signal(contract, manifest)
        name = manifest.get("name", provider_id)
        if not isinstance(name, str):
            name = provider_id

        return ProviderResolution(
            provider_id=provider_id,
            name=name,
            api_style=api_style,
            chat_path=chat_path,
            source=source,
            contract=contract,
            manifest=manifest,
            event_map=event_map,
            streaming_done_signal=streaming_done_signal,
        )

    def list_provider_summaries(self) -> list[dict[str, Any]]:
        """Build /providers payload using resolver (replaces path heuristics)."""
        rows: list[dict[str, Any]] = []
        for provider_id, _ in self._manifests.items():
            try:
                res = self.resolve(provider_id)
            except KeyError:
                continue
            capability_profile = res.manifest.get("capability_profile")
            has_capability_profile = isinstance(capability_profile, dict)
            phase = capability_profile.get("phase") if has_capability_profile else None
            has_ios_dimensions = False
            if has_capability_profile:
                has_ios_dimensions = any(key in capability_profile for key in ("inputs", "outcomes", "systems"))
            rows.append(
                {
                    "provider_id": res.provider_id,
                    "api_style": res.public_api_style(),
                    "chat_path": res.chat_path,
                    "name": res.name,
                    "has_capability_profile": has_capability_profile,
                    "capability_profile_phase": phase,
                    "has_ios_dimensions": has_ios_dimensions,
                    "resolution_source": res.source,
                }
            )
        return rows


def _streaming_done_signal(contract: dict[str, Any] | None, manifest: dict[str, Any]) -> str | None:
    if contract:
        cap = contract.get("capability_contracts")
        if isinstance(cap, dict):
            streaming = cap.get("streaming")
            if isinstance(streaming, dict):
                done = streaming.get("done_signal")
                if isinstance(done, str):
                    return done
    streaming = manifest.get("streaming")
    if isinstance(streaming, dict):
        decoder = streaming.get("decoder")
        if isinstance(decoder, dict):
            done = decoder.get("done_signal")
            if isinstance(done, str):
                return done
    return None
