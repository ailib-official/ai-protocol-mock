# ai-protocol-mock v0.1.3 Release Notes

**Release Date**: 2026-02-19

## Summary

Protocol alignment with ai-protocol: full Cohere v2 rerank response format, v2 provider manifest loading, sync script for v2/providers.

## What's New

### Rerank Mock — Cohere v2 Compliant

- Rerank endpoint returns full Cohere v2 format: `results`, `id`, `meta` (api_version, billed_units)

### Manifest Loading

- Loads from `v2/providers` in addition to `v1/providers`

### Sync Script

- `sync_manifests.py` adds `v2/providers` to sync paths

### Code Quality

- Chinese module headers for all Python modules
