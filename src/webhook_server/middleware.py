"""Middleware for logging, rate limiting, and monitoring."""

import time
import logging
from typing import Callable
from collections import defaultdict, deque

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests and responses."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """Log request and response.

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response
        """
        start_time = time.time()

        # Log request
        logger.info(
            f"Request: {request.method} {request.url.path} "
            f"from {request.client.host if request.client else 'unknown'}"
        )

        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            logger.error(f"Request failed: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"error": "Internal server error"}
            )

        # Log response
        duration = (time.time() - start_time) * 1000  # ms
        logger.info(
            f"Response: {response.status_code} "
            f"for {request.method} {request.url.path} "
            f"({duration:.2f}ms)"
        )

        # Add processing time header
        response.headers["X-Process-Time"] = f"{duration:.2f}ms"

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple rate limiting middleware using sliding window."""

    def __init__(
        self,
        app,
        max_requests: int = 100,
        window_seconds: int = 60
    ):
        """Initialize rate limiter.

        Args:
            app: FastAPI application
            max_requests: Maximum requests per window
            window_seconds: Time window in seconds
        """
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: defaultdict[str, deque] = defaultdict(deque)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """Check rate limit before processing request.

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response or 429 Too Many Requests
        """
        # Skip rate limiting for health checks
        if request.url.path == "/health":
            return await call_next(request)

        # Get client identifier (IP address)
        client_id = request.client.host if request.client else "unknown"

        # Get current time
        now = time.time()

        # Clean old requests outside the window
        request_times = self.requests[client_id]
        while request_times and request_times[0] < now - self.window_seconds:
            request_times.popleft()

        # Check rate limit
        if len(request_times) >= self.max_requests:
            logger.warning(
                f"Rate limit exceeded for {client_id}: "
                f"{len(request_times)} requests in {self.window_seconds}s"
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "retry_after": int(request_times[0] + self.window_seconds - now)
                }
            )

        # Add current request time
        request_times.append(now)

        # Process request
        return await call_next(request)
