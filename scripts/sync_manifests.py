#!/usr/bin/env python3
"""Sync manifest files from ai-protocol main repository.

Downloads v1/providers, v1/models, schemas from GitHub raw URL to manifests/.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

# Default sync URL (ai-protocol main)
DEFAULT_SYNC_URL = "https://raw.githubusercontent.com/hiddenpath/ai-protocol/main/"
MANIFEST_DIR = Path(__file__).resolve().parents[1] / "manifests"

# Paths to sync (relative to repo root)
SYNC_PATHS = [
    "v1/providers",
    "v1/models",
    "schemas",
]


def download_file(url: str, dest: Path) -> bool:
    """Download a single file, return True on success."""
    try:
        resp = httpx.get(url, follow_redirects=True, timeout=30)
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
        "v1/providers": ["openai.yaml", "anthropic.yaml", "gemini.yaml"],
        "v1/models": [],  # May be empty or we discover from providers
        "schemas": ["v1/provider.json", "v2/provider.json", "v2/endpoint.json", "v2/capabilities.json", "v2/errors.json"],
    }
    # Flatten: also try v2/ subdir
    extra = {
        "schemas/v2": ["provider.json", "endpoint.json", "capabilities.json", "errors.json", "message.json"],
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

    # Try to discover provider yamls from directory listing via API
    if rel_path == "v1/providers":
        api_url = "https://api.github.com/repos/hiddenpath/ai-protocol/contents/v1/providers"
        try:
            r = httpx.get(api_url, timeout=10)
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
        except Exception:
            pass

    return success, fail


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync manifests from ai-protocol")
    parser.add_argument(
        "--url",
        default=DEFAULT_SYNC_URL,
        help="Base URL for sync (default: ai-protocol main)",
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
    global MANIFEST_DIR
    MANIFEST_DIR = Path(args.output_dir)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)

    total_ok, total_fail = 0, 0
    for path in SYNC_PATHS:
        ok, fail = sync_path(args.url, path, args.force)
        total_ok += ok
        total_fail += fail

    # Write sync metadata for version check (used by /status endpoint)
    from datetime import datetime
    meta = {
        "synced_from": args.url.rstrip("/"),
        "paths": SYNC_PATHS,
        "synced_at": datetime.utcnow().isoformat() + "Z",
    }
    (MANIFEST_DIR / "_sync_meta.json").write_text(json.dumps(meta, indent=2))

    print(f"Sync complete: {total_ok} ok, {total_fail} failed")
    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
