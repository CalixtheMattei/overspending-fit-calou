from __future__ import annotations

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

# POST endpoints that are provably read-only (no DB writes, no file I/O).
# /imports/preview  — single SELECT on Transaction.fingerprint, pure stats
# /rules/preview    — savepoint + full rollback, nothing persisted
_READONLY_POST_PATHS: frozenset[str] = frozenset({
    "/imports/preview",
    "/rules/preview",
})

_MUTATING_METHODS: frozenset[str] = frozenset({"POST", "PATCH", "PUT", "DELETE"})


class DemoGuardMiddleware(BaseHTTPMiddleware):
    """Block state-mutating HTTP requests when the app runs in demo mode."""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        if request.method in _MUTATING_METHODS:
            path = request.url.path.rstrip("/")
            if path not in _READONLY_POST_PATHS:
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "This action is disabled in demo mode.",
                        "demo_mode": True,
                    },
                )
        return await call_next(request)
