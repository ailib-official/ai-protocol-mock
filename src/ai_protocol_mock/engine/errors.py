"""Error injection for mock HTTP endpoints (MOCK-001-R2).

Mock HTTP 端点错误注入（X-Mock-Error 等测试头）。
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse, Response


def apply_mock_error(request: Request, *, stream: bool = False) -> Response | None:
    """Return an error response when X-Mock-Error is set, else None."""
    error_kind = request.headers.get("x-mock-error", "").strip().lower()
    if not error_kind:
        return None

    if error_kind == "context_overflow":
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "message": "This model's maximum context length is 128000 tokens.",
                    "type": "invalid_request_error",
                    "code": "context_length_exceeded",
                }
            },
        )

    if error_kind == "content_filter":
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "message": "Content was filtered by the provider safety system.",
                    "type": "invalid_request_error",
                    "code": "content_filter",
                }
            },
        )

    if error_kind == "rate_limit":
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "message": "Rate limit exceeded.",
                    "type": "rate_limit_error",
                    "code": "rate_limit_exceeded",
                }
            },
            headers={"retry-after": "5"},
        )

    if error_kind == "stream_interrupt" and stream:
        # Signal to caller: truncate stream without terminal [DONE].
        return _StreamInterruptMarker()

    return None


class _StreamInterruptMarker(Response):
    """Sentinel response: stream should end early without [DONE]."""

    def __init__(self) -> None:
        super().__init__(content="", status_code=200)


def is_stream_interrupt(response: Response | None) -> bool:
    return isinstance(response, _StreamInterruptMarker)
