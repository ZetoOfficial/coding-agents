"""FastAPI application for GitHub webhook server."""

import logging
from datetime import datetime
from typing import Dict, Any

from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse
from redis import Redis
from rq import Queue

from src.common.config import AgentConfig, load_config, setup_logging
from src.webhook_server.webhook_handler import WebhookHandler, get_webhook_payload
from src.webhook_server.event_router import EventRouter
from src.webhook_server.middleware import RequestLoggingMiddleware, RateLimitMiddleware
from src.webhook_server.models import (
    WebhookResponse,
    HealthResponse,
    CICompletePayload
)

logger = logging.getLogger(__name__)

# Initialize app
app = FastAPI(
    title="Coding Agents Webhook Server",
    description="GitHub App webhook server for automated SDLC",
    version="0.1.0"
)

# Global state
config: AgentConfig = None
redis_conn: Redis = None
webhook_handler: WebhookHandler = None
event_router: EventRouter = None


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize application on startup."""
    global config, redis_conn, webhook_handler, event_router

    # Load configuration
    config = load_config()
    setup_logging(config)

    logger.info("Starting Coding Agents Webhook Server")
    logger.info(f"Using GitHub App: {config.is_using_github_app()}")
    logger.info(f"Repository: {config.github_repository}")

    # Initialize Redis connection
    if not config.redis_url:
        raise ValueError("REDIS_URL not configured")

    redis_conn = Redis.from_url(
        config.redis_url,
        decode_responses=False  # RQ requires bytes mode
    )

    # Test Redis connection
    try:
        redis_conn.ping()
        logger.info("Redis connection successful")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise

    # Initialize webhook handler and event router
    webhook_handler = WebhookHandler(config)
    event_router = EventRouter(config, redis_conn)

    logger.info("Webhook server startup complete")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Cleanup on shutdown."""
    global redis_conn

    logger.info("Shutting down webhook server")

    if redis_conn:
        redis_conn.close()
        logger.info("Redis connection closed")


# Add middleware
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    RateLimitMiddleware,
    max_requests=100,  # 100 requests
    window_seconds=60   # per minute
)


@app.get("/")
async def root() -> Dict[str, str]:
    """Root endpoint."""
    return {
        "service": "Coding Agents Webhook Server",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint.

    Returns:
        HealthResponse with service health status
    """
    checks = {}

    # Check Redis
    try:
        redis_conn.ping()
        checks["redis"] = True
    except Exception:
        checks["redis"] = False

    # Check RQ queue
    try:
        queue = Queue("agent-tasks", connection=redis_conn)
        checks["rq"] = True
        checks["queue_size"] = len(queue)
    except Exception:
        checks["rq"] = False

    # Overall status
    status = "healthy" if all([
        checks.get("redis", False),
        checks.get("rq", False)
    ]) else "unhealthy"

    return HealthResponse(
        status=status,
        timestamp=datetime.utcnow(),
        checks=checks
    )


@app.post("/webhooks/github", response_model=WebhookResponse)
async def github_webhook(request: Request) -> WebhookResponse:
    """Handle GitHub webhook events.

    Args:
        request: FastAPI request with webhook payload

    Returns:
        WebhookResponse with processing status
    """
    try:
        # Extract and verify payload
        event_type, payload, raw_body = await get_webhook_payload(request)

        # Verify signature
        signature = request.headers.get("X-Hub-Signature-256")
        webhook_handler.verify_signature(raw_body, signature)

        # Parse event
        event_type, parsed_payload = webhook_handler.parse_event(event_type, payload)

        # Route event to appropriate handler
        response = event_router.route_event(event_type, parsed_payload)

        return response

    except Exception as e:
        logger.error(f"Webhook processing failed: {e}", exc_info=True)
        return WebhookResponse(
            success=False,
            message=f"Webhook processing failed: {str(e)}"
        )


@app.post("/webhooks/ci-complete", response_model=WebhookResponse)
async def ci_complete_webhook(payload: CICompletePayload) -> WebhookResponse:
    """Handle CI completion webhook (triggers AI review).

    This endpoint is called by GitHub Actions after CI checks complete.

    Args:
        payload: CI completion payload with PR number and artifacts URL

    Returns:
        WebhookResponse with task information
    """
    try:
        logger.info(
            f"Received CI complete notification for PR #{payload.pr_number} "
            f"in {payload.repository}"
        )

        # Get installation ID (assuming single installation for now)
        # In production, you'd look this up from the repository
        installation_id = config.github_app_installation_id
        if not installation_id:
            raise ValueError("Installation ID not configured")

        # Convert config to dict for serialization (with secrets exposed)
        config_dict = config.to_dict_with_secrets()

        # Enqueue review task
        queue = Queue("agent-tasks", connection=redis_conn)
        job = queue.enqueue(
            "src.webhook_server.tasks.review_pr_task",
            pr_number=payload.pr_number,
            repository=payload.repository,
            installation_id=installation_id,
            config_dict=config_dict,
            artifacts_url=payload.artifacts_url,
            job_timeout="15m",
            result_ttl=86400
        )

        logger.info(
            f"Enqueued PR review: #{payload.pr_number} "
            f"in {payload.repository}, job_id={job.id}"
        )

        return WebhookResponse(
            success=True,
            message=f"PR review enqueued for #{payload.pr_number}",
            task_id=job.id,
            details={
                "pr_number": payload.pr_number,
                "repository": payload.repository,
                "artifacts_url": payload.artifacts_url
            }
        )

    except Exception as e:
        logger.error(f"CI complete webhook failed: {e}", exc_info=True)
        return WebhookResponse(
            success=False,
            message=f"Failed to enqueue review: {str(e)}"
        )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler.

    Args:
        request: Request that caused the exception
        exc: The exception

    Returns:
        JSON error response
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc)
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.webhook_server.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
