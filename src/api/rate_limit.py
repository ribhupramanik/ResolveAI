from collections import deque
from math import ceil
from re import fullmatch
from threading import Lock
from time import monotonic

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class AIRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        max_requests: int = 10,
        window_seconds: int = 60,
        max_daily_requests: int = 30,
        daily_window_seconds: int = 86400,
        max_concurrent_requests: int | None = None,
    ):
        super().__init__(app)

        if any(
            value <= 0
            for value in (
                max_requests,
                window_seconds,
                max_daily_requests,
                daily_window_seconds,
            )
        ):
            raise ValueError("Rate limit values must be positive.")

        if max_concurrent_requests is not None and max_concurrent_requests <= 0:
            raise ValueError("Concurrent request limit must be positive.")

        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.max_daily_requests = max_daily_requests
        self.daily_window_seconds = daily_window_seconds
        self.max_concurrent_requests = max_concurrent_requests

        self.timestamps = deque()
        self.daily_timestamps = deque()
        self.active_requests = 0
        self.lock = Lock()

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        is_chat = path == "/api/v1/chat"

        is_conversation_message = (
            fullmatch(
                r"/api/v1/conversations/[^/]+/messages",
                path,
            )
            is not None
        )

        if request.method != "POST" or not (is_chat or is_conversation_message):
            return await call_next(request)

        now = monotonic()

        with self.lock:
            cutoff = now - self.window_seconds
            daily_cutoff = now - self.daily_window_seconds

            while self.timestamps and self.timestamps[0] <= cutoff:
                self.timestamps.popleft()

            while self.daily_timestamps and self.daily_timestamps[0] <= daily_cutoff:
                self.daily_timestamps.popleft()

            if len(self.timestamps) >= self.max_requests:
                retry_after = max(
                    1,
                    ceil(self.window_seconds - (now - self.timestamps[0])),
                )

                return JSONResponse(
                    status_code=429,
                    content={"detail": "AI request rate limit exceeded."},
                    headers={"Retry-After": str(retry_after)},
                )

            if len(self.daily_timestamps) >= self.max_daily_requests:
                retry_after = max(
                    1,
                    ceil(self.daily_window_seconds - (now - self.daily_timestamps[0])),
                )

                return JSONResponse(
                    status_code=429,
                    content={"detail": "Daily AI request budget exceeded."},
                    headers={"Retry-After": str(retry_after)},
                )

            if (
                self.max_concurrent_requests is not None
                and self.active_requests >= self.max_concurrent_requests
            ):
                return JSONResponse(
                    status_code=503,
                    content={"detail": "AI service is busy. Try again shortly."},
                    headers={"Retry-After": "1"},
                )

            self.timestamps.append(now)
            self.daily_timestamps.append(now)
            self.active_requests += 1

        try:
            return await call_next(request)
        finally:
            with self.lock:
                self.active_requests -= 1
