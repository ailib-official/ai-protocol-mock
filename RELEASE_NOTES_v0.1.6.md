# ai-protocol-mock v0.1.6 Release Notes

**Release Date**: 2026-02-19

## Summary

Docker PyPI support: install from PyPI in Docker, `sync-manifests` entry point, easy upgrade via `docker compose build --no-cache`.

## What's New

### Docker from PyPI

- Dockerfile now installs `ai-protocol-mock` from PyPI instead of local source
- Build arg `MOCK_VERSION` to pin version: `docker build --build-arg MOCK_VERSION=0.1.6`
- Omit `MOCK_VERSION` for latest: `docker compose build --no-cache`

### sync-manifests Entry Point

- `sync-manifests` console script installed with the package
- Supports `--output-dir` for Docker volume mounts (e.g. `/app/manifests`)
- Scripts included in wheel for PyPI installs

### Upgrade Flow

```bash
# Rebuild to get latest from PyPI
docker compose build --no-cache
docker compose up -d --force-recreate
```

## Upgrade

```bash
pip install -U ai-protocol-mock
```
