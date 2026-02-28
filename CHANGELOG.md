# Changelog

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
