#!/usr/bin/env python3
"""Sync manifest files from ai-protocol main repository.

从 ai-protocol 主仓库同步 manifest 文件。
Downloads v1/providers, v2/providers, v1/models, schemas from GitHub raw URL to manifests/.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

# Default sync URL (ai-protocol main)
# Default sync URL — PROTO-PIN tip (post PT-ARCH-005c; gemini canonical)
DEFAULT_SYNC_URL = "https://raw.githubusercontent.com/ailib-official/ai-protocol/749cb825c99f03e9dc737294b41fd5f5552533b4/"
MANIFEST_DIR = Path(__file__).resolve().parents[1] / "manifests"


def _resolve_sync_url(url: str, tag: str | None) -> str:
    """Use tag/branch if provided. E.g. --tag v0.7.1 pins to that release."""
    if not tag:
        return url.rstrip("/")
    return f"https://raw.githubusercontent.com/ailib-official/ai-protocol/{tag}/"


# Paths to sync (relative to repo root)
SYNC_PATHS = [
    "v1/providers",
    "v2/providers",
    "v2/contracts",
    "v1/models",
    "schemas",
]


def download_file(url: str, dest: Path) -> bool:
    """Download a single file, return True on success."""
    try:
        resp = httpx.get(url, follow_redirects=True, timeout=30, trust_env=False)
        resp.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(resp.content)
        return True
    except Exception as e:
        print(f"  Failed {url}: {e}", file=sys.stderr)
        return False


def sync_path(base_url: str, rel_path: str, force: bool) -> tuple[int, int]:
    """Sync a directory path. Returns (success_count, fail_count)."""
    # GitHub raw doesn't support directory listing; we use the GitHub API or known file list
    # For simplicity, we try common patterns
    known_files = {
        "v1/providers": ["openai.yaml", "anthropic.yaml"],
        "v2/providers": [
            "openai.yaml",
            "anthropic.yaml",
            "gemini.yaml",
            "deepseek.yaml",
            "qwen.yaml",
            "doubao.yaml",
            "cohere.yaml",
            "moonshot.yaml",
            "zhipu.yaml",
            "jina.yaml",
        ],
        "v1/models": [],  # May be empty or we discover from providers
        "schemas": [
            "v1.json",
            "spec.json",
            "v2/provider.json",
            "v2/endpoint.json",
            "v2/capabilities.json",
            "v2/errors.json",
            "v2/capability-profile.json",
        ],
    }
    # Flatten: also try v2/ subdir
    extra = {
        "schemas/v2": [
            "provider.json",
            "endpoint.json",
            "availability.json",
            "capabilities.json",
            "errors.json",
            "regions.json",
            "mcp.json",
            "computer-use.json",
            "multimodal.json",
            "provider-contract.json",
            "context-policy.json",
            "pricing.json",
            "message-roles.json",
            "capability-profile.json",
        ],
    }
    success, fail = 0, 0
    base = base_url.rstrip("/")
    dest_base = MANIFEST_DIR / rel_path

    files_to_try = known_files.get(rel_path, [])
    for f in files_to_try:
        url = f"{base}/{rel_path}/{f}"
        dest = dest_base / f
        if dest.exists() and not force:
            success += 1
            continue
        if download_file(url, dest):
            success += 1
        else:
            fail += 1

    for subpath, filenames in extra.items():
        for f in filenames:
            url = f"{base}/{subpath}/{f}"
            dest = MANIFEST_DIR / subpath / f
            if dest.exists() and not force:
                success += 1
                continue
            if download_file(url, dest):
                success += 1
            else:
                fail += 1

    # Discover provider yamls from GitHub API (v1 and v2 providers)
    if rel_path == "v1/providers":
        api_url = "https://api.github.com/repos/ailib-official/ai-protocol/contents/v1/providers"
        try:
            r = httpx.get(api_url, timeout=15, trust_env=False)
            if r.status_code == 200:
                for item in r.json():
                    if item.get("type") == "file" and item.get("name", "").endswith((".yaml", ".yml")):
                        name = item["name"]
                        url = f"{base}/v1/providers/{name}"
                        dest = MANIFEST_DIR / "v1" / "providers" / name
                        if dest.exists() and not force:
                            success += 1
                        elif download_file(url, dest):
                            success += 1
                        else:
                            fail += 1
        except Exception as e:
            print(f"  GitHub API discovery failed: {e}", file=sys.stderr)

    if rel_path == "v2/providers":
        api_url = "https://api.github.com/repos/ailib-official/ai-protocol/contents/v2/providers"
        try:
            r = httpx.get(api_url, timeout=15, trust_env=False)
            if r.status_code == 200:
                for item in r.json():
                    if item.get("type") == "file" and item.get("name", "").endswith((".yaml", ".yml")):
                        name = item["name"]
                        url = f"{base}/v2/providers/{name}"
                        dest = MANIFEST_DIR / "v2" / "providers" / name
                        if dest.exists() and not force:
                            success += 1
                        elif download_file(url, dest):
                            success += 1
                        else:
                            fail += 1
        except Exception as e:
            print(f"  GitHub API discovery for v2 providers failed: {e}", file=sys.stderr)

    if rel_path == "v2/contracts":
        api_url = "https://api.github.com/repos/ailib-official/ai-protocol/contents/v2/contracts"
        try:
            r = httpx.get(api_url, timeout=15, trust_env=False)
            if r.status_code == 200:
                for item in r.json():
                    if item.get("type") == "file" and item.get("name", "").endswith((".yaml", ".yml")):
                        name = item["name"]
                        url = f"{base}/v2/contracts/{name}"
                        dest = MANIFEST_DIR / "v2" / "contracts" / name
                        if dest.exists() and not force:
                            success += 1
                        elif download_file(url, dest):
                            success += 1
                        else:
                            fail += 1
        except Exception as e:
            print(f"  GitHub API discovery for v2 contracts failed: {e}", file=sys.stderr)

    # Discover v1/models from GitHub API
    if rel_path == "v1/models":
        api_url = "https://api.github.com/repos/ailib-official/ai-protocol/contents/v1/models"
        try:
            r = httpx.get(api_url, timeout=15, trust_env=False)
            if r.status_code == 200:
                for item in r.json():
                    if item.get("type") == "file" and item.get("name", "").endswith((".yaml", ".yml")):
                        name = item["name"]
                        url = f"{base}/v1/models/{name}"
                        dest = MANIFEST_DIR / "v1" / "models" / name
                        if dest.exists() and not force:
                            success += 1
                        elif download_file(url, dest):
                            success += 1
                        else:
                            fail += 1
        except Exception as e:
            print(f"  GitHub API discovery for models failed: {e}", file=sys.stderr)

    return success, fail


def main() -> int:
    global MANIFEST_DIR
    parser = argparse.ArgumentParser(description="Sync manifests from ai-protocol")
    parser.add_argument(
        "--url",
        default=DEFAULT_SYNC_URL,
        help="Base URL for sync (default: ai-protocol main)",
    )
    parser.add_argument(
        "--tag",
        metavar="REF",
        help="Use specific ai-protocol ref (e.g. v0.7.1, main) instead of --url",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files",
    )
    parser.add_argument(
        "--output-dir",
        default=str(MANIFEST_DIR),
        help="Output directory for manifests",
    )
    args = parser.parse_args()
    MANIFEST_DIR = Path(args.output_dir)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)

    sync_url = _resolve_sync_url(args.url, args.tag)

    total_ok, total_fail = 0, 0
    for path in SYNC_PATHS:
        ok, fail = sync_path(sync_url, path, args.force)
        total_ok += ok
        total_fail += fail

    # Write sync metadata for version check (used by /status endpoint)
    meta = {
        "synced_from": sync_url,
        "paths": SYNC_PATHS,
        "synced_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "tag": args.tag,
    }
    (MANIFEST_DIR / "_sync_meta.json").write_text(json.dumps(meta, indent=2))

    print(f"Sync complete: {total_ok} ok, {total_fail} failed")
    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
