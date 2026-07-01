"""Load ProviderContract YAML files from v2/contracts.

从 v2/contracts 加载 ProviderContract YAML。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class ContractRegistry:
    """Index of provider contracts keyed by provider_id."""

    def __init__(self, manifest_dir: Path) -> None:
        self._contracts: dict[str, dict[str, Any]] = {}
        contracts_dir = manifest_dir / "v2" / "contracts"
        if contracts_dir.is_dir():
            for path in sorted(contracts_dir.glob("*.yaml")):
                try:
                    data = yaml.safe_load(path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if not isinstance(data, dict):
                    continue
                pid = data.get("provider_id")
                if isinstance(pid, str) and pid:
                    self._contracts[pid] = data
            for path in sorted(contracts_dir.glob("*.contract.yaml")):
                try:
                    data = yaml.safe_load(path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if not isinstance(data, dict):
                    continue
                pid = data.get("provider_id")
                if isinstance(pid, str) and pid:
                    self._contracts[pid] = data

    def get_for_provider(self, provider_id: str) -> dict[str, Any] | None:
        return self._contracts.get(provider_id)

    def provider_ids(self) -> set[str]:
        return set(self._contracts)
