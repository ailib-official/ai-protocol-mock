# ai-protocol-mock v0.1.4 Release Notes

**Release Date**: 2026-02-19

## Summary

Docker build fix: correct install order and README inclusion for reliable container deployment (e.g. Raspberry Pi).

## What's New

### Dockerfile Fixes

- **COPY README.md** before pip install — hatchling requires README.md for metadata
- **Copy src/ before pip install** — install package with full source, fix `ModuleNotFoundError: ai_protocol_mock`
- **Use `pip install .`** instead of editable install for production containers

### Verification

```bash
docker compose up -d --build
curl http://localhost:4010/health
```
