"""Pydantic models for webhook payloads and responses."""

from typing import Optional, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field


class WebhookUser(BaseModel):
    """GitHub user in webhook payload."""

    login: str
    id: int
    type: str


class WebhookRepository(BaseModel):
    """GitHub repository in webhook payload."""

    id: int
    name: str
    full_name: str
    owner: WebhookUser
    private: bool
    default_branch: str = "main"


class WebhookIssue(BaseModel):
    """GitHub issue in webhook payload."""

    id: int
    number: int
    title: str
    body: Optional[str] = None
    state: str
    user: WebhookUser
    labels: list[Dict[str, Any]] = []
    created_at: datetime
    updated_at: datetime


class WebhookPullRequest(BaseModel):
    """GitHub pull request in webhook payload."""

    id: int
    number: int
    title: str
    body: Optional[str] = None
    state: str
    user: WebhookUser
    head: Dict[str, Any]
    base: Dict[str, Any]
    merged: bool = False
    labels: list[Dict[str, Any]] = []
    created_at: datetime
    updated_at: datetime


class WebhookComment(BaseModel):
    """GitHub comment in webhook payload."""

    id: int
    body: str
    user: WebhookUser
    created_at: datetime


class WebhookReview(BaseModel):
    """GitHub PR review in webhook payload."""

    id: int
    user: WebhookUser
    body: Optional[str] = None
    state: str  # "approved", "changes_requested", "commented"
    submitted_at: datetime


class IssuesEventPayload(BaseModel):
    """Payload for issues webhook events."""

    action: Literal["opened", "edited", "closed", "reopened", "labeled", "unlabeled"]
    issue: WebhookIssue
    repository: WebhookRepository
    sender: WebhookUser
    label: Optional[Dict[str, Any]] = None
    installation: Optional[Dict[str, Any]] = None


class IssueCommentEventPayload(BaseModel):
    """Payload for issue_comment webhook events."""

    action: Literal["created", "edited", "deleted"]
    issue: WebhookIssue
    comment: WebhookComment
    repository: WebhookRepository
    sender: WebhookUser
    installation: Optional[Dict[str, Any]] = None


class PullRequestEventPayload(BaseModel):
    """Payload for pull_request webhook events."""

    action: Literal["opened", "edited", "closed", "reopened", "synchronize"]
    number: int
    pull_request: WebhookPullRequest
    repository: WebhookRepository
    sender: WebhookUser
    installation: Optional[Dict[str, Any]] = None


class PullRequestReviewEventPayload(BaseModel):
    """Payload for pull_request_review webhook events."""

    action: Literal["submitted", "edited", "dismissed"]
    review: WebhookReview
    pull_request: WebhookPullRequest
    repository: WebhookRepository
    sender: WebhookUser
    installation: Optional[Dict[str, Any]] = None


class PingEventPayload(BaseModel):
    """Payload for ping webhook events (sent when webhook is created)."""

    zen: str
    hook_id: int
    hook: Dict[str, Any]
    repository: Optional[WebhookRepository] = None
    sender: Optional[WebhookUser] = None


class CICompletePayload(BaseModel):
    """Custom payload for CI completion notification."""

    pr_number: int
    repository: str
    artifacts_url: str


class WebhookResponse(BaseModel):
    """Standard webhook response."""

    success: bool
    message: str
    task_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: Literal["healthy", "unhealthy"]
    timestamp: datetime
    version: str = "0.1.0"
    checks: Dict[str, bool] = Field(default_factory=dict)
