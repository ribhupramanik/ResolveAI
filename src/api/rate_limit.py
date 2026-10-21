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
    ):
        super().__init__(app)

        if max_requests < 1 or window_seconds <= 0:
            raise ValueError("Rate limit values must be positive.")

        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.timestamps = deque()
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

            while self.timestamps and self.timestamps[0] <= cutoff:
                self.timestamps.popleft()

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

            self.timestamps.append(now)

        return await call_next(request)
