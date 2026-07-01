"""Tests for MOCK-001-R1 registry and contract resolver."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_protocol_mock.engine.resolver import ContractResolver, ProviderResolution
from ai_protocol_mock.registry.contracts import ContractRegistry
from ai_protocol_mock.registry.manifests import ManifestRegistry

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "r1"


@pytest.fixture
def fixture_root(tmp_path: Path) -> Path:
    """Minimal manifest + contract tree for R1 tests."""
    v2p = tmp_path / "v2" / "providers"
    v2p.mkdir(parents=True)
    contracts = tmp_path / "v2" / "contracts"
    contracts.mkdir(parents=True)

    (v2p / "openai.yaml").write_text(
        yaml.dump(
            {
                "id": "openai",
                "name": "OpenAI",
                "endpoint": {"chat": "/chat/completions"},
                "streaming": {"decoder": {"strategy": "openai_chat", "format": "sse"}},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (v2p / "anthropic.yaml").write_text(
        yaml.dump(
            {
                "id": "anthropic",
                "name": "Anthropic",
                "endpoint": {"chat": "/messages"},
                "streaming": {"decoder": {"strategy": "anthropic_event_stream", "format": "sse"}},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (v2p / "google.yaml").write_text(
        yaml.dump(
            {
                "id": "google",
                "name": "Google",
                "endpoint": {"chat": "/v1beta/models/{model}:generateContent"},
                "streaming": {"decoder": {"strategy": "gemini_generate", "format": "sse"}},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (contracts / "anthropic-messages.contract.yaml").write_text(
        yaml.dump(
            {
                "provider_id": "anthropic",
                "api_style": "anthropic_messages",
                "capability_contracts": {"streaming": {"protocol": "sse", "done_signal": "message_stop"}},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (contracts / "gemini-generate.contract.yaml").write_text(
        yaml.dump(
            {
                "provider_id": "google",
                "api_style": "gemini_generate",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return tmp_path


def test_manifest_registry_loads_v2_providers(fixture_root: Path) -> None:
    reg = ManifestRegistry(fixture_root)
    assert reg.provider_ids() == {"anthropic", "google", "openai"}
    openai = reg.get("openai")
    assert openai is not None
    assert reg.chat_path(openai) == "/chat/completions"


def test_contract_registry_loads_by_provider_id(fixture_root: Path) -> None:
    reg = ContractRegistry(fixture_root)
    anthropic = reg.get_for_provider("anthropic")
    assert anthropic is not None
    assert anthropic["api_style"] == "anthropic_messages"


def test_resolver_uses_contract_api_style_for_anthropic(fixture_root: Path) -> None:
    resolver = ContractResolver(fixture_root)
    res = resolver.resolve("anthropic")
    assert isinstance(res, ProviderResolution)
    assert res.api_style == "anthropic_messages"
    assert res.chat_path == "/messages"
    assert res.streaming_done_signal == "message_stop"
    assert res.source == "contract"


def test_resolver_uses_decoder_strategy_when_no_contract_file(fixture_root: Path) -> None:
    resolver = ContractResolver(fixture_root)
    res = resolver.resolve("openai")
    assert res.api_style == "openai_chat"
    assert res.source == "manifest_decoder"


def test_resolver_merges_contract_and_manifest_for_google(fixture_root: Path) -> None:
    resolver = ContractResolver(fixture_root)
    res = resolver.resolve("google")
    assert res.api_style == "gemini_generate"
    assert res.source == "contract"


def test_resolver_unknown_provider_raises(fixture_root: Path) -> None:
    resolver = ContractResolver(fixture_root)
    with pytest.raises(KeyError, match="unknown-provider"):
        resolver.resolve("unknown-provider")


def test_resolver_openai_event_map_from_manifest(fixture_root: Path) -> None:
    """OpenAI manifest in repo includes event_map; resolver should expose it when present."""
    repo_manifests = Path(__file__).resolve().parents[1] / "manifests"
    if not (repo_manifests / "v2" / "providers" / "openai.yaml").exists():
        pytest.skip("synced manifests not present")
    resolver = ContractResolver(repo_manifests)
    res = resolver.resolve("openai")
    assert res.event_map is not None
    assert len(res.event_map) >= 1
    emits = {e.get("emit") for e in res.event_map if isinstance(e, dict)}
    assert "PartialContentDelta" in emits


def test_list_resolutions_sorted(fixture_root: Path) -> None:
    resolver = ContractResolver(fixture_root)
    rows = resolver.list_provider_summaries()
    ids = [r["provider_id"] for r in rows]
    assert ids == sorted(ids)
    anthropic_row = next(r for r in rows if r["provider_id"] == "anthropic")
    assert anthropic_row["api_style"] == "anthropic_messages"


def test_resolver_jina_rerank_only_from_repo_manifests() -> None:
    """Jina is rerank-only (no chat decoder); must still appear in /providers summaries."""
    repo_manifests = Path(__file__).resolve().parents[1] / "manifests"
    jina_path = repo_manifests / "v2" / "providers" / "jina.yaml"
    if not jina_path.exists():
        pytest.skip("synced manifests not present")
    resolver = ContractResolver(repo_manifests)
    res = resolver.resolve("jina")
    assert res.api_style == "rerank"
    assert res.source == "manifest_rerank"
    assert res.chat_path == "/v1/rerank"
    rows = resolver.list_provider_summaries()
    assert "jina" in {row["provider_id"] for row in rows}
