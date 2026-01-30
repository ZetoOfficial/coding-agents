"""GitHub webhook handler with signature verification."""

import hmac
import hashlib
import logging
from typing import Optional, Dict, Any

from fastapi import Request, HTTPException, Header

from src.common.config import AgentConfig

logger = logging.getLogger(__name__)


class WebhookHandler:
    """Handles GitHub webhook signature verification and event parsing."""

    def __init__(self, config: AgentConfig):
        """Initialize webhook handler.

        Args:
            config: Agent configuration with webhook secret
        """
        self.webhook_secret = config.get_webhook_secret()
        if not self.webhook_secret:
            logger.warning("Webhook secret not configured - signature verification disabled")

    def verify_signature(
        self,
        payload_body: bytes,
        signature_header: Optional[str]
    ) -> bool:
        """Verify GitHub webhook signature.

        Args:
            payload_body: Raw request body
            signature_header: X-Hub-Signature-256 header value

        Returns:
            True if signature is valid, False otherwise

        Raises:
            HTTPException: If signature is missing or invalid
        """
        if not self.webhook_secret:
            logger.warning("Skipping signature verification (no secret configured)")
            return True

        if not signature_header:
            logger.error("Missing X-Hub-Signature-256 header")
            raise HTTPException(status_code=401, detail="Missing signature header")

        # GitHub sends signature as "sha256=<hash>"
        if not signature_header.startswith("sha256="):
            logger.error(f"Invalid signature format: {signature_header[:20]}")
            raise HTTPException(status_code=401, detail="Invalid signature format")

        signature_parts = signature_header.split("=")
        if len(signature_parts) != 2:
            logger.error("Invalid signature format")
            raise HTTPException(status_code=401, detail="Invalid signature format")

        expected_signature = signature_parts[1]

        # Calculate HMAC
        mac = hmac.new(
            self.webhook_secret.encode(),
            msg=payload_body,
            digestmod=hashlib.sha256
        )
        calculated_signature = mac.hexdigest()

        # Compare signatures using constant-time comparison
        if not hmac.compare_digest(calculated_signature, expected_signature):
            logger.error("Signature verification failed")
            raise HTTPException(status_code=401, detail="Invalid signature")

        logger.debug("Signature verification successful")
        return True

    def parse_event(
        self,
        event_type: Optional[str],
        payload: Dict[str, Any]
    ) -> tuple[str, Dict[str, Any]]:
        """Parse webhook event and extract relevant information.

        Args:
            event_type: X-GitHub-Event header value
            payload: Parsed JSON payload

        Returns:
            Tuple of (event_type, parsed_payload)

        Raises:
            HTTPException: If event type is missing or unsupported
        """
        if not event_type:
            logger.error("Missing X-GitHub-Event header")
            raise HTTPException(status_code=400, detail="Missing event type header")

        supported_events = [
            "ping",
            "issues",
            "issue_comment",
            "pull_request",
            "pull_request_review"
        ]

        if event_type not in supported_events:
            logger.warning(f"Unsupported event type: {event_type}")
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported event type: {event_type}"
            )

        logger.info(
            f"Received {event_type} event: "
            f"action={payload.get('action', 'N/A')}, "
            f"repo={payload.get('repository', {}).get('full_name', 'N/A')}"
        )

        return event_type, payload


async def get_webhook_payload(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
    x_github_event: Optional[str] = Header(None, alias="X-GitHub-Event")
) -> tuple[str, Dict[str, Any], bytes]:
    """Extract and verify webhook payload from request.

    Args:
        request: FastAPI request object
        x_hub_signature_256: GitHub signature header
        x_github_event: GitHub event type header

    Returns:
        Tuple of (event_type, payload_dict, raw_body)

    Raises:
        HTTPException: If verification fails or payload is invalid
    """
    # Read raw body for signature verification
    raw_body = await request.body()

    # Parse JSON payload
    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse JSON payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    return x_github_event, payload, raw_body
