# Changelog

## Unreleased

## 0.1.9 - 2026-03-08

### Added

- **Video generation terminal-state lifecycle**: async polling now supports deterministic terminal variants `succeeded` / `failed` / `cancelled`.
- **Terminal-state controls**: `X-Mock-Video-Terminal` header and request `terminal_state` parameter for targeted scenario injection.
- **Lifecycle documentation updates**: README now documents state machine and new test-control headers.

### Changed

- Async video job polling remains stable after terminal state is reached to avoid flaky test semantics.
- Extended test coverage for failed/cancelled terminal states in `tests/test_mock.py`.

### Added

- **Video generation mock lifecycle**: added `POST /v1/video/generations` and `GET /v1/video/generations/{job_id}` with deterministic async polling transitions (`queued -> running -> succeeded`)
- **Failure simulation controls**: added generic test headers for timeout and invalid content type injection (`X-Mock-Timeout-Ms`, `X-Mock-Invalid-Content-Type`)
- **Coverage expansion**: added tests for video sync/async/not-found paths and failure injection behavior

## 0.1.8 - 2026-02-28

### Fixed

- **Manifest sync robustness**: sync script now aligns with latest ai-protocol schema layout and avoids stale schema file assumptions
- **Network environment stability**: sync requests ignore proxy env by default to avoid proxy-related failures in local/CI runs
- **Python runtime compatibility**: fixed global declaration ordering and updated datetime usage in sync tooling

### Validation

- **Cross-runtime smoke verification**: minimal integration checks executed for ai-lib-rust, ai-lib-python, and ai-lib-ts against mock + v2-related path

## 0.1.7 - 2026-02-20

### Added

- **Third-party integration**: README section for ZeroClaw/ZeroSpider and CI usage
- **Third-party integration (中文)**: README_CN 第三方集成章节

## 0.1.6 - (previous)
