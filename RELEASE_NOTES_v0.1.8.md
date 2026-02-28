# ai-protocol-mock v0.1.8 Release Notes

**Release Date**: 2026-02-28

## Summary

This release improves manifest sync reliability after recent ai-protocol v2 schema updates and confirms runtime compatibility via smoke checks.

## What's Fixed

### Sync tooling robustness

- Updated schema sync targets to match current `ai-protocol` layout
- Removed stale schema assumptions in sync logic
- Fixed Python global declaration ordering issue
- Updated datetime usage to modern UTC API

### Stable network behavior

- Disabled implicit proxy-env usage for sync HTTP requests to reduce local/CI proxy failures

## Validation

- `ai-lib-rust`: minimal mock integration smoke test
- `ai-lib-python`: minimal mock integration smoke test
- `ai-lib-ts`: minimal mock integration smoke test

## Upgrade

```bash
pip install -U ai-protocol-mock==0.1.8
```
