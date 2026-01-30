"""Reviewer Agent Orchestrator - business logic separated from CLI.

This module contains the core business logic for PR review.
It can be called from both CLI and webhook tasks.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from src.code_agent.github_client import GitHubClient
from src.common.config import AgentConfig
from src.common.models import PullRequest, ReviewComment, ReviewOutput
from src.reviewer_agent.analysis_engine import (
    analyze_pr_diff,
    check_requirements_fulfillment,
    generate_line_comments,
)
from src.reviewer_agent.ci_analyzer import categorize_failures, parse_ci_artifacts

logger = logging.getLogger(__name__)


# Helper functions (moved from reviewer.py)


def _parse_diff_to_dict(diff: str, file_paths: list[str]) -> dict[str, Any]:
    """Parse unified diff into structured dictionary.

    Args:
        diff: Unified diff string
        file_paths: List of changed file paths

    Returns:
        Dictionary with file patches for positioning
    """
    files = {}

    current_file = None
    current_patch = []

    for line in diff.split("\n"):
        # Detect file header
        if line.startswith("diff --git"):
            # Save previous file
            if current_file:
                files[current_file] = "\n".join(current_patch)

            # Extract file path
            match = line.split(" b/")
            if len(match) > 1:
                current_file = match[1]
                current_patch = []
        elif current_file:
            current_patch.append(line)

    # Save last file
    if current_file:
        files[current_file] = "\n".join(current_patch)

    return {"files": files}


def _extract_iteration_from_labels(labels: list[str]) -> int:
    """Extract iteration number from PR labels.

    Args:
        labels: List of label names

    Returns:
        Iteration number (default 1)
    """
    for label in labels:
        match = re.match(r"iteration-(\d+)", label.lower())
        if match:
            return int(match.group(1))

    return 1


def _format_summary_comment(review: ReviewOutput) -> str:
    """Format review output as summary comment.

    Args:
        review: ReviewOutput model

    Returns:
        Formatted markdown summary
    """
    lines = [
        f"# AI Code Review - Iteration {review.iteration}",
        "",
        f"**Status**: {'✅ Approved' if review.approve else '❌ Changes Requested'}",
        f"**Quality Score**: {review.overall_quality_score:.1f}/10",
        "",
        "## Summary",
        review.summary,
        "",
    ]

    if review.blocking_issues:
        lines.append("## 🚫 Blocking Issues")
        for issue in review.blocking_issues:
            lines.append(f"- {issue}")
        lines.append("")

    if review.non_blocking_issues:
        lines.append("## ⚠️ Non-Blocking Issues")
        for issue in review.non_blocking_issues:
            lines.append(f"- {issue}")
        lines.append("")

    if review.ci_summary:
        lines.append("## CI Results")
        for key, value in review.ci_summary.items():
            lines.append(f"- **{key}**: {value}")
        lines.append("")

    if review.requirements_fulfilled:
        fulfilled = sum(review.requirements_fulfilled)
        total = len(review.requirements_fulfilled)
        lines.append(f"## Requirements: {fulfilled}/{total} fulfilled")
        lines.append("")

    lines.append("---")
    lines.append(f"*Generated at {review.timestamp.isoformat()}*")

    return "\n".join(lines)


def _map_approval_to_decision(approve: bool, blocking_issues: list[str]) -> str:
    """Map approval decision to string.

    Args:
        approve: Approval flag
        blocking_issues: List of blocking issues

    Returns:
        Decision string: "approve", "request_changes", or "comment"
    """
    if blocking_issues:
        return "request_changes"
    elif approve:
        return "approve"
    else:
        return "comment"


def _empty_ci_results() -> dict[str, Any]:
    """Return empty CI results for graceful degradation.

    Returns:
        Empty CI results dictionary
    """
    return {
        "pytest": {"status": "skipped", "passed": 0, "failed": 0, "total": 0},
        "ruff": {"errors": []},
        "mypy": {"errors": []},
        "bandit": {"issues": []},
        "pip_audit": {"vulnerabilities": []},
        "coverage": {"total_percent": 0.0},
    }


@dataclass
class ReviewResult:
    """Result of PR review."""

    success: bool
    decision: str | None = None  # "approve", "request_changes", "comment"
    issues_count: int = 0
    error: str | None = None
    review_output: ReviewOutput | None = None


class ReviewerOrchestrator:
    """Orchestrates PR review operations."""

    def __init__(self, config: AgentConfig):
        """Initialize orchestrator.

        Args:
            config: Agent configuration
        """
        self.config = config
        logger.info("Initialized ReviewerOrchestrator")

    def _determine_outcome(
        self,
        ci_results: dict[str, Any],
        categorized_failures: dict[str, list[dict[str, Any]]],
        requirements_fulfilled: dict[str, bool],
        diff_analysis: dict[str, Any],
    ) -> dict[str, Any]:
        """Determine review outcome based on CI and analysis.

        Args:
            ci_results: Raw CI results from parse_ci_artifacts
            categorized_failures: Categorized failures from categorize_failures
            requirements_fulfilled: Requirement fulfillment mapping
            diff_analysis: Analysis from analyze_pr_diff

        Returns:
            Dictionary with outcome decision
        """
        blocking_issues = []
        non_blocking_issues = []
        approve = True
        quality_score = 10.0

        # Check test failures (blocking)
        test_failures = categorized_failures.get("tests", [])
        if test_failures:
            approve = False
            blocking_issues.append(f"Tests failing: {len(test_failures)} test(s) failed")
            quality_score -= 3.0

        # Check lint errors (blocking if errors, not warnings)
        lint_errors = categorized_failures.get("lint", [])
        if lint_errors:
            error_count = len([e for e in lint_errors if e.get("severity") == "error"])
            if error_count > 0:
                approve = False
                blocking_issues.append(f"Linting errors: {error_count} error(s) found")
                quality_score -= 2.0
            else:
                non_blocking_issues.append(f"Linting warnings: {len(lint_errors)} warning(s)")
                quality_score -= 0.5

        # Check type errors (blocking)
        type_errors = categorized_failures.get("types", [])
        if type_errors:
            approve = False
            blocking_issues.append(f"Type errors: {len(type_errors)} error(s) found")
            quality_score -= 2.0

        # Check security issues (blocking if HIGH severity)
        security_issues = categorized_failures.get("security", [])
        high_severity_security = [s for s in security_issues if s.get("severity") == "HIGH"]
        if high_severity_security:
            approve = False
            blocking_issues.append(
                f"High-severity security issues: {len(high_severity_security)} found"
            )
            quality_score -= 3.0
        elif security_issues:
            non_blocking_issues.append(
                f"Security concerns: {len(security_issues)} issue(s) to review"
            )
            quality_score -= 1.0

        # Check dependency vulnerabilities (non-blocking for now)
        dep_vulns = categorized_failures.get("dependencies", [])
        if dep_vulns:
            non_blocking_issues.append(f"Dependency vulnerabilities: {len(dep_vulns)} found")
            quality_score -= 0.5

        # Check requirements fulfillment
        if requirements_fulfilled:
            total_reqs = len(requirements_fulfilled)
            fulfilled = sum(requirements_fulfilled.values())
            if fulfilled < total_reqs:
                unfulfilled = total_reqs - fulfilled
                approve = False
                blocking_issues.append(
                    f"Requirements not met: {unfulfilled}/{total_reqs} requirements appear unfulfilled"
                )
                quality_score -= 2.0

        # Add issues from diff analysis
        potential_issues = diff_analysis.get("potential_issues", [])
        if potential_issues:
            non_blocking_issues.extend(potential_issues)
            quality_score -= 0.5

        # Ensure quality score is in valid range
        quality_score = max(0.0, min(10.0, quality_score))

        return {
            "approve": approve,
            "blocking_issues": blocking_issues,
            "non_blocking_issues": non_blocking_issues,
            "quality_score": quality_score,
        }

    def _generate_review_with_line_comments(
        self,
        outcome: dict[str, Any],
        ci_results: dict[str, Any],
        categorized_failures: dict[str, list[dict[str, Any]]],
        diff_analysis: dict[str, Any],
        requirements_fulfilled: dict[str, bool],
        line_comments: list[ReviewComment],
        pr: PullRequest,
    ) -> ReviewOutput:
        """Generate comprehensive review output with summary and line comments.

        Args:
            outcome: Outcome from _determine_outcome
            ci_results: Raw CI results
            categorized_failures: Categorized failures
            diff_analysis: Diff analysis results
            requirements_fulfilled: Requirements fulfillment mapping
            line_comments: Generated line comments
            pr: PullRequest object

        Returns:
            Complete ReviewOutput model
        """
        # Get iteration from PR labels
        label_names = [label.name for label in pr.labels]
        iteration = _extract_iteration_from_labels(label_names)

        # Build summary
        summary_parts = [diff_analysis.get("summary", "No summary available")]

        if outcome["approve"]:
            summary_parts.append("\n\nThis PR looks good and meets all requirements!")
        else:
            summary_parts.append("\n\nThis PR requires changes before it can be approved.")

        summary = "\n".join(summary_parts)

        # Build CI summary
        ci_summary = {
            "tests": f"{ci_results.get('pytest', {}).get('passed', 0)}/{ci_results.get('pytest', {}).get('total', 0)} passed",
            "lint_errors": len(categorized_failures.get("lint", [])),
            "type_errors": len(categorized_failures.get("types", [])),
            "security_issues": len(categorized_failures.get("security", [])),
            "coverage": f"{ci_results.get('coverage', {}).get('total_percent', 0):.1f}%",
        }

        # Requirements fulfilled list (boolean list matching requirements order)
        requirements_fulfilled_list = (
            list(requirements_fulfilled.values()) if requirements_fulfilled else []
        )

        return ReviewOutput(
            approve=outcome["approve"],
            summary=summary,
            blocking_issues=outcome["blocking_issues"],
            non_blocking_issues=outcome["non_blocking_issues"],
            line_comments=line_comments,
            requirements_fulfilled=requirements_fulfilled_list,
            overall_quality_score=outcome["quality_score"],
            ci_summary=ci_summary,
            iteration=iteration,
            timestamp=datetime.utcnow(),
        )

    def analyze_pull_request(self, pr_number: int, artifact_dir: str | None = None) -> ReviewOutput:
        """Analyze PR and generate review without posting to GitHub.

        Args:
            pr_number: GitHub PR number
            artifact_dir: Directory with CI artifacts (optional)

        Returns:
            ReviewOutput with complete review data
        """
        logger.info(f"Starting analysis of PR #{pr_number}")

        github_client = None
        try:
            # Initialize GitHub client
            github_client = GitHubClient(self.config)

            # Fetch PR
            pr = github_client.fetch_pull_request(pr_number)
            logger.info(f"Analyzing PR: {pr.title}")

            # Fetch issue (automatic extraction from pr.issue_number)
            issue = None
            requirements = []
            if pr.issue_number:
                try:
                    issue = github_client.fetch_issue(pr.issue_number)
                    requirements = issue.requirements
                    logger.info(
                        f"Found {len(requirements)} requirements from issue #{pr.issue_number}"
                    )
                except Exception as e:
                    logger.warning(f"Could not fetch issue: {e}")

            # Get PR diff and files
            diff = github_client.get_pr_diff(pr_number)
            files_changed = github_client.get_pr_files_changed(pr_number)
            file_paths = [fc.path for fc in files_changed]

            logger.info(f"PR has {len(files_changed)} changed files")

            # Parse CI artifacts with graceful degradation
            if artifact_dir and Path(artifact_dir).exists():
                try:
                    ci_results = parse_ci_artifacts(artifact_dir)
                    categorized_failures = categorize_failures(ci_results)
                    logger.info(
                        f"Parsed CI: {len(categorized_failures.get('tests', []))} test failures"
                    )
                except Exception as e:
                    logger.warning(f"Failed to parse CI artifacts: {e}")
                    ci_results = _empty_ci_results()
                    categorized_failures = {}
            else:
                logger.warning("No artifacts provided, proceeding without CI data")
                ci_results = _empty_ci_results()
                categorized_failures = {}

            # Analyze diff
            pr_data = {"diff": diff, "files_changed": file_paths}
            diff_analysis = analyze_pr_diff(diff, requirements, self.config)

            # Check requirements
            requirements_fulfilled = {}
            if requirements:
                requirements_fulfilled = check_requirements_fulfillment(pr_data, requirements)

            # Generate line comments
            diff_data = _parse_diff_to_dict(diff, file_paths)
            line_comments = generate_line_comments(categorized_failures, diff_data)

            # Determine outcome
            outcome = self._determine_outcome(
                ci_results=ci_results,
                categorized_failures=categorized_failures,
                requirements_fulfilled=requirements_fulfilled,
                diff_analysis=diff_analysis,
            )

            # Build review
            review = self._generate_review_with_line_comments(
                outcome=outcome,
                ci_results=ci_results,
                categorized_failures=categorized_failures,
                diff_analysis=diff_analysis,
                requirements_fulfilled=requirements_fulfilled,
                line_comments=line_comments,
                pr=pr,
            )

            logger.info(
                f"Review complete: approve={review.approve}, "
                f"blocking={len(review.blocking_issues)}, "
                f"comments={len(review.line_comments)}"
            )

            return review

        except Exception as e:
            logger.error(f"Failed to analyze PR #{pr_number}: {e}", exc_info=True)
            # Return failure review instead of raising
            return ReviewOutput(
                approve=False,
                summary=f"Review failed due to error: {str(e)}",
                blocking_issues=[f"Automated review encountered an error: {str(e)}"],
                non_blocking_issues=[],
                line_comments=[],
                requirements_fulfilled=[],
                overall_quality_score=0.0,
                ci_summary={"error": str(e)},
                iteration=1,
            )
        finally:
            if github_client:
                github_client.close()

    def post_review(self, pr_number: int, review: ReviewOutput) -> None:
        """Post review to GitHub PR idempotently.

        Args:
            pr_number: GitHub PR number
            review: ReviewOutput to post

        Raises:
            Exception if posting fails
        """
        logger.info(f"Posting review to PR #{pr_number}")

        github_client = None
        try:
            github_client = GitHubClient(self.config)

            # Dismiss old bot reviews
            github_client.dismiss_old_bot_reviews(pr_number)

            # Determine event type
            if review.blocking_issues:
                event = "REQUEST_CHANGES"
            else:
                event = "COMMENT"  # Bots cannot APPROVE

            # Post review
            github_client.post_review(pr_number, review, event)

            # Post summary comment
            summary_text = _format_summary_comment(review)
            github_client.post_summary_comment_idempotent(pr_number, summary_text)

            logger.info(f"Review posted successfully: {event}")

        finally:
            if github_client:
                github_client.close()

    def review_pull_request(
        self, pr_number: int, artifact_dir: str | None = None, post_review: bool = True
    ) -> ReviewResult:
        """Review pull request and optionally post to GitHub.

        This is the main entry point for webhook tasks.

        Args:
            pr_number: Pull request number
            artifact_dir: Directory with CI artifacts (optional)
            post_review: Whether to post review to GitHub

        Returns:
            ReviewResult with success status and details
        """
        logger.info(f"Reviewing PR #{pr_number} (post={post_review})")

        try:
            # Analyze PR
            review_output = self.analyze_pull_request(pr_number, artifact_dir)

            # Check if analysis failed
            if review_output.overall_quality_score == 0.0 and review_output.blocking_issues:
                # Analysis produced error
                error_msg = (
                    review_output.blocking_issues[0]
                    if review_output.blocking_issues
                    else "Unknown error"
                )
                if "error" in error_msg.lower():
                    return ReviewResult(success=False, error=error_msg, review_output=review_output)

            # Post review if requested
            if post_review:
                try:
                    self.post_review(pr_number, review_output)
                except Exception as e:
                    logger.error(f"Failed to post review: {e}", exc_info=True)
                    return ReviewResult(
                        success=False,
                        error=f"Analysis succeeded but posting failed: {str(e)}",
                        decision="error",
                        issues_count=len(review_output.blocking_issues)
                        + len(review_output.non_blocking_issues),
                        review_output=review_output,
                    )

            # Success
            return ReviewResult(
                success=True,
                decision=_map_approval_to_decision(
                    review_output.approve, review_output.blocking_issues
                ),
                issues_count=len(review_output.blocking_issues)
                + len(review_output.non_blocking_issues),
                review_output=review_output,
            )

        except Exception as e:
            logger.error(f"Review failed: {e}", exc_info=True)
            return ReviewResult(success=False, error=str(e))
