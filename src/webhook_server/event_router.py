"""Route webhook events to appropriate tasks."""

import logging
from typing import Any

from redis import Redis
from rq import Queue

from src.common.config import AgentConfig
from src.webhook_server.models import (
    IssueCommentEventPayload,
    IssuesEventPayload,
    PullRequestEventPayload,
    PullRequestReviewEventPayload,
    WebhookResponse,
)

logger = logging.getLogger(__name__)


class EventRouter:
    """Routes GitHub webhook events to RQ tasks."""

    def __init__(self, config: AgentConfig, redis_conn: Redis):
        """Initialize event router.

        Args:
            config: Agent configuration
            redis_conn: Redis connection for RQ
        """
        self.config = config
        self.queue = Queue("agent-tasks", connection=redis_conn)

    def route_event(
        self,
        event_type: str,
        payload: dict[str, Any]
    ) -> WebhookResponse:
        """Route event to appropriate handler.

        Args:
            event_type: GitHub event type
            payload: Event payload

        Returns:
            WebhookResponse with task information
        """
        if event_type == "ping":
            return self._handle_ping(payload)
        elif event_type == "issues":
            return self._handle_issues_event(payload)
        elif event_type == "issue_comment":
            return self._handle_issue_comment_event(payload)
        elif event_type == "pull_request":
            return self._handle_pull_request_event(payload)
        elif event_type == "pull_request_review":
            return self._handle_pull_request_review_event(payload)
        else:
            logger.warning(f"Unsupported event type: {event_type}")
            return WebhookResponse(
                success=False,
                message=f"Unsupported event type: {event_type}"
            )

    def _handle_ping(self, payload: dict[str, Any]) -> WebhookResponse:
        """Handle ping event (webhook test).

        Args:
            payload: Ping event payload

        Returns:
            WebhookResponse
        """
        logger.info(f"Received ping: {payload.get('zen', 'N/A')}")
        return WebhookResponse(
            success=True,
            message="Pong! Webhook is configured correctly",
            details={"zen": payload.get("zen")}
        )

    def _handle_issues_event(self, payload_dict: dict[str, Any]) -> WebhookResponse:
        """Handle issues event.

        Triggers code agent when issue is labeled with 'agent:implement'.

        Args:
            payload_dict: Issues event payload

        Returns:
            WebhookResponse
        """
        try:
            payload = IssuesEventPayload(**payload_dict)
        except Exception as e:
            logger.error(f"Failed to parse issues event payload: {e}")
            return WebhookResponse(success=False, message=f"Invalid payload: {e}")

        # Check if issue was labeled with agent:implement
        if payload.action == "labeled" and payload.label:
            label_name = payload.label.get("name", "")
            if label_name == "agent:implement":
                return self._enqueue_issue_processing(payload)

        return WebhookResponse(
            success=True,
            message=f"Issue {payload.action} - no action needed",
            details={"action": payload.action}
        )

    def _handle_issue_comment_event(
        self,
        payload_dict: dict[str, Any]
    ) -> WebhookResponse:
        """Handle issue comment event.

        Triggers code agent when comment contains '/agent implement'.

        Args:
            payload_dict: Issue comment event payload

        Returns:
            WebhookResponse
        """
        try:
            payload = IssueCommentEventPayload(**payload_dict)
        except Exception as e:
            logger.error(f"Failed to parse issue_comment event payload: {e}")
            return WebhookResponse(success=False, message=f"Invalid payload: {e}")

        # Check for /agent implement command
        if payload.action == "created":
            comment_body = payload.comment.body.strip().lower()
            if "/agent implement" in comment_body:
                # Convert to IssuesEventPayload format for processing
                fake_issues_payload = IssuesEventPayload(
                    action="labeled",
                    issue=payload.issue,
                    repository=payload.repository,
                    sender=payload.sender,
                    installation=payload.installation
                )
                return self._enqueue_issue_processing(fake_issues_payload)

        return WebhookResponse(
            success=True,
            message=f"Comment {payload.action} - no action needed"
        )

    def _handle_pull_request_event(
        self,
        payload_dict: dict[str, Any]
    ) -> WebhookResponse:
        """Handle pull request event.

        Triggers reviewer agent when PR is opened or synchronized.

        Args:
            payload_dict: Pull request event payload

        Returns:
            WebhookResponse
        """
        try:
            payload = PullRequestEventPayload(**payload_dict)
        except Exception as e:
            logger.error(f"Failed to parse pull_request event payload: {e}")
            return WebhookResponse(success=False, message=f"Invalid payload: {e}")

        # Trigger review for opened/synchronized PRs
        if payload.action in ["opened", "synchronize", "reopened"]:
            # Note: We wait for CI to complete before triggering AI review
            # This event is logged but actual review is triggered by CI complete webhook
            logger.info(
                f"PR #{payload.number} {payload.action} - "
                f"waiting for CI to complete before review"
            )

        return WebhookResponse(
            success=True,
            message=f"PR {payload.action} - waiting for CI",
            details={"pr_number": payload.number, "action": payload.action}
        )

    def _handle_pull_request_review_event(
        self,
        payload_dict: dict[str, Any]
    ) -> WebhookResponse:
        """Handle pull request review event.

        Triggers feedback loop when reviewer requests changes.

        Args:
            payload_dict: Pull request review event payload

        Returns:
            WebhookResponse
        """
        try:
            payload = PullRequestReviewEventPayload(**payload_dict)
        except Exception as e:
            logger.error(f"Failed to parse pull_request_review event payload: {e}")
            return WebhookResponse(success=False, message=f"Invalid payload: {e}")

        # Trigger feedback loop for change requests
        if payload.action == "submitted" and payload.review.state == "changes_requested":
            return self._enqueue_feedback_application(payload)

        return WebhookResponse(
            success=True,
            message=f"Review {payload.action} ({payload.review.state}) - no action needed"
        )

    def _enqueue_issue_processing(
        self,
        payload: IssuesEventPayload
    ) -> WebhookResponse:
        """Enqueue issue processing task.

        Args:
            payload: Issues event payload

        Returns:
            WebhookResponse with task ID
        """
        installation_id = payload.installation.get("id") if payload.installation else None
        if not installation_id:
            logger.error("Missing installation ID in payload")
            return WebhookResponse(
                success=False,
                message="Missing installation ID"
            )

        # Convert config to dict for serialization (with secrets exposed)
        config_dict = self.config.to_dict_with_secrets()

        # Debug logging for serialized private key
        private_key = config_dict.get("github_app_private_key")
        if private_key:
            literal_newline = "\\n"
            has_literal = isinstance(private_key, str) and literal_newline in private_key
            has_real = isinstance(private_key, str) and chr(10) in private_key
            logger.debug(
                f"Serialized config: private_key type={type(private_key).__name__}, "
                f"length={len(private_key) if isinstance(private_key, str) else 'N/A'}, "
                f"has_literal_backslash_n={has_literal}, "
                f"has_real_newline={has_real}"
            )

        # Enqueue task
        job = self.queue.enqueue(
            "src.webhook_server.tasks.process_issue_task",
            issue_number=payload.issue.number,
            repository=payload.repository.full_name,
            installation_id=installation_id,
            config_dict=config_dict,
            force=False,
            job_timeout="30m",
            result_ttl=86400  # Keep results for 24 hours
        )

        logger.info(
            f"Enqueued issue processing: #{payload.issue.number} "
            f"in {payload.repository.full_name}, job_id={job.id}"
        )

        return WebhookResponse(
            success=True,
            message=f"Issue processing enqueued for #{payload.issue.number}",
            task_id=job.id,
            details={
                "issue_number": payload.issue.number,
                "repository": payload.repository.full_name
            }
        )

    def _enqueue_feedback_application(
        self,
        payload: PullRequestReviewEventPayload
    ) -> WebhookResponse:
        """Enqueue feedback application task.

        Args:
            payload: Pull request review event payload

        Returns:
            WebhookResponse with task ID
        """
        installation_id = payload.installation.get("id") if payload.installation else None
        if not installation_id:
            logger.error("Missing installation ID in payload")
            return WebhookResponse(
                success=False,
                message="Missing installation ID"
            )

        # Convert config to dict for serialization (with secrets exposed)
        config_dict = self.config.to_dict_with_secrets()

        # Debug logging for serialized private key
        private_key = config_dict.get("github_app_private_key")
        if private_key:
            literal_newline = "\\n"
            has_literal = isinstance(private_key, str) and literal_newline in private_key
            has_real = isinstance(private_key, str) and chr(10) in private_key
            logger.debug(
                f"Serialized config: private_key type={type(private_key).__name__}, "
                f"length={len(private_key) if isinstance(private_key, str) else 'N/A'}, "
                f"has_literal_backslash_n={has_literal}, "
                f"has_real_newline={has_real}"
            )

        # Enqueue task
        job = self.queue.enqueue(
            "src.webhook_server.tasks.apply_feedback_task",
            pr_number=payload.pull_request.number,
            repository=payload.repository.full_name,
            installation_id=installation_id,
            config_dict=config_dict,
            job_timeout="30m",
            result_ttl=86400
        )

        logger.info(
            f"Enqueued feedback application: PR #{payload.pull_request.number} "
            f"in {payload.repository.full_name}, job_id={job.id}"
        )

        return WebhookResponse(
            success=True,
            message=f"Feedback application enqueued for PR #{payload.pull_request.number}",
            task_id=job.id,
            details={
                "pr_number": payload.pull_request.number,
                "repository": payload.repository.full_name
            }
        )
