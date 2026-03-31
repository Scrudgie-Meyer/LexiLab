"""
lexilab — middleware
Rate limiting + request size validation.
"""

import time
from collections import defaultdict
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# ─────────────────────────────────────────────
# LIMITS
# ─────────────────────────────────────────────
MAX_TEXT_LENGTH   = 100_000   # символів
MAX_REQUEST_BODY  = 200_000   # байт (~200KB)
RATE_LIMIT_COUNT  = 30        # запитів
RATE_LIMIT_WINDOW = 3600      # секунд (1 година)

# Ендпоінти з rate limiting
RATE_LIMITED_PATHS = {"/analyze/", "/analyze"}


# ─────────────────────────────────────────────
# IN-MEMORY RATE LIMITER
# Для продакшну краще використати Redis,
# але для Railway free tier це достатньо
# ─────────────────────────────────────────────
class RateLimiter:
    def __init__(self):
        # { ip: [(timestamp, count), ...] }
        self._requests: dict[str, list] = defaultdict(list)

    def is_allowed(self, ip: str, path: str) -> tuple[bool, int]:
        """
        Перевіряє чи дозволено запит.
        Повертає (allowed, remaining).
        """
        now = time.time()
        window_start = now - RATE_LIMIT_WINDOW

        # прибираємо старі записи
        self._requests[ip] = [
            ts for ts in self._requests[ip]
            if ts > window_start
        ]

        count = len(self._requests[ip])
        remaining = max(0, RATE_LIMIT_COUNT - count)

        if count >= RATE_LIMIT_COUNT:
            return False, 0

        self._requests[ip].append(now)
        return True, remaining - 1

    def reset_ip(self, ip: str):
        self._requests.pop(ip, None)


rate_limiter = RateLimiter()


# ─────────────────────────────────────────────
# MIDDLEWARE
# ─────────────────────────────────────────────
class LexilabMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):

        # ── 1. перевірка розміру запиту ──
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_REQUEST_BODY:
            return JSONResponse(
                status_code=413,
                content={
                    "error": "Request too large",
                    "detail": f"Maximum request size is {MAX_REQUEST_BODY // 1000}KB",
                }
            )

        # ── 2. rate limiting тільки для /analyze ──
        path = request.url.path
        method = request.method

        if method == "POST" and path.rstrip("/") in {"/analyze", ""}:
            # беремо IP з заголовків (Railway проксі)
            ip = (
                request.headers.get("x-forwarded-for", "").split(",")[0].strip()
                or request.headers.get("x-real-ip", "")
                or request.client.host
            )

            allowed, remaining = rate_limiter.is_allowed(ip, path)

            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Rate limit exceeded",
                        "detail": f"Maximum {RATE_LIMIT_COUNT} analyze requests per hour. Try again later.",
                    },
                    headers={
                        "X-RateLimit-Limit":     str(RATE_LIMIT_COUNT),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Window":    f"{RATE_LIMIT_WINDOW}s",
                        "Retry-After":           str(RATE_LIMIT_WINDOW),
                    }
                )

            response = await call_next(request)
            response.headers["X-RateLimit-Limit"]     = str(RATE_LIMIT_COUNT)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Window"]    = f"{RATE_LIMIT_WINDOW}s"
            return response

        return await call_next(request)
