"""Pydantic models for data structures used throughout the system."""

from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field


class IssueLabel(BaseModel):
    """GitHub issue/PR label."""

    name: str
    color: str = ""
    description: str = ""


class IssueRequirement(BaseModel):
    """A single requirement extracted from an issue."""

    description: str
    fulfilled: bool = False
    evidence: Optional[str] = None


class Issue(BaseModel):
    """GitHub issue representation."""

    number: int
    title: str
    body: str
    state: Literal["open", "closed"]
    labels: List[IssueLabel] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    user: str
    html_url: str

    # Extracted information
    requirements: List[str] = Field(default_factory=list)
    acceptance_criteria: List[str] = Field(default_factory=list)
    technical_constraints: List[str] = Field(default_factory=list)
    target_files: List[str] = Field(default_factory=list)
    complexity: Optional[Literal["simple", "medium", "complex"]] = None


class PullRequest(BaseModel):
    """GitHub pull request representation."""

    number: int
    title: str
    body: str
    state: Literal["open", "closed", "merged"]
    head_branch: str
    base_branch: str
    labels: List[IssueLabel] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    html_url: str
    mergeable: Optional[bool] = None

    # Associated issue
    issue_number: Optional[int] = None


class FileChange(BaseModel):
    """Represents a change to a file."""

    path: str
    change_type: Literal["added", "modified", "deleted"]
    additions: int = 0
    deletions: int = 0
    content: Optional[str] = None
    patch: Optional[str] = None


class CodeGeneration(BaseModel):
    """Structured output for LLM code generation."""

    explanation: str = Field(description="What changes are being made and why")
    files_to_modify: Optional[Dict[str, str]] = Field(
        default=None, description="Mapping of file paths to new content"
    )
    files_to_create: Optional[Dict[str, str]] = Field(
        default=None, description="Mapping of new file paths to content"
    )
    dependencies_needed: Optional[List[str]] = Field(
        default=None, description="New dependencies to add"
    )


class RequirementAnalysis(BaseModel):
    """Structured output for issue analysis."""

    requirements: List[str] = Field(
        description="List of specific requirements extracted from issue"
    )
    acceptance_criteria: List[str] = Field(
        description="How to verify the implementation"
    )
    technical_constraints: List[str] = Field(
        description="Technical limitations or requirements"
    )
    target_files: List[str] = Field(
        description="Files that likely need modification"
    )
    complexity: Literal["simple", "medium", "complex"] = Field(
        description="Estimated complexity"
    )


class CIResult(BaseModel):
    """Results from a CI check."""

    name: str
    status: Literal["success", "failure", "pending", "unknown"]
    conclusion: Optional[Literal["success", "failure", "neutral", "cancelled", "timed_out"]] = (
        None
    )
    details: Dict[str, Any] = Field(default_factory=dict)


class SecurityIssue(BaseModel):
    """Security issue detected by analysis."""

    severity: Literal["HIGH", "MEDIUM", "LOW"]
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    test_id: str
    test_name: str
    filename: str
    line: int
    code: str
    message: str


class LintError(BaseModel):
    """Linting error."""

    file: str
    line: int
    column: int = 0
    code: str
    message: str
    severity: Literal["error", "warning"] = "error"


class TestFailure(BaseModel):
    """Test failure information."""

    test_name: str
    file: str
    line: Optional[int] = None
    message: str
    traceback: Optional[str] = None


class ReviewComment(BaseModel):
    """Inline review comment on a PR."""

    path: str
    position: Optional[int] = None  # Position in diff
    line: Optional[int] = None  # Absolute line number
    body: str
    severity: Literal["blocking", "non-blocking", "suggestion"] = "non-blocking"


class ReviewOutput(BaseModel):
    """Structured output for code review."""

    approve: bool
    summary: str
    blocking_issues: List[str] = Field(default_factory=list)
    non_blocking_issues: List[str] = Field(default_factory=list)
    line_comments: List[ReviewComment] = Field(default_factory=list)
    requirements_fulfilled: List[bool] = Field(default_factory=list)
    overall_quality_score: float = Field(default=5.0, ge=0.0, le=10.0)

    # CI results summary
    ci_summary: Dict[str, Any] = Field(default_factory=dict)

    # Metadata
    iteration: int = 1
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AgentState(BaseModel):
    """State tracking for an issue/PR iteration."""

    issue_number: int
    pr_number: Optional[int] = None
    iteration: int = 1
    status: Literal["pending", "in_progress", "completed", "failed", "stuck"] = "pending"

    # History tracking
    errors: List[str] = Field(default_factory=list)
    fixes_attempted: List[str] = Field(default_factory=list)
    review_history: List[Dict[str, Any]] = Field(default_factory=list)

    # Timestamps
    started_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FeedbackInterpretation(BaseModel):
    """Interpretation of reviewer feedback for fixes."""

    what_went_wrong: str
    how_to_fix: str
    files_to_modify: List[str]
    priority: Literal["high", "medium", "low"] = "high"
