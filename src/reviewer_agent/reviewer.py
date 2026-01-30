"""Main reviewer agent orchestrator for automated PR review.

This module provides the entry point for the AI reviewer agent that runs
in GitHub Actions. It analyzes PR changes, CI results, and requirements
to generate comprehensive code reviews.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

import click

from src.common.config import AgentConfig, load_config
from src.common.models import ReviewOutput, ReviewComment, Issue, PullRequest
from src.code_agent.github_client import GitHubClient
from src.code_agent.llm_client import call_llm_structured, call_llm_text
from src.reviewer_agent.ci_analyzer import parse_ci_artifacts, categorize_failures
from src.reviewer_agent.analysis_engine import (
    analyze_pr_diff,
    check_requirements_fulfillment,
    generate_line_comments,
)

logger = logging.getLogger(__name__)


def analyze_pr(
    pr_number: int,
    issue_number: Optional[int],
    artifact_dir: str,
    config: AgentConfig,
) -> ReviewOutput:
    """Analyze a pull request and generate comprehensive review.

    Main orchestration function that:
    1. Fetches PR and issue data
    2. Parses CI artifacts
    3. Analyzes code changes
    4. Checks requirement fulfillment
    5. Generates review with line comments

    Args:
        pr_number: GitHub PR number
        issue_number: Associated issue number (optional)
        artifact_dir: Directory containing CI artifacts
        config: Agent configuration

    Returns:
        ReviewOutput model with complete review data
    """
    logger.info(f"Starting analysis of PR #{pr_number}")

    github_client = GitHubClient(config)

    try:
        # Fetch PR data
        pr = github_client.fetch_pull_request(pr_number)
        logger.info(f"Analyzing PR: {pr.title}")

        # Fetch associated issue if available
        issue = None
        requirements = []
        acceptance_criteria = []

        if issue_number or pr.issue_number:
            issue_num = issue_number or pr.issue_number
            try:
                issue = github_client.fetch_issue(issue_num)
                requirements = issue.requirements
                acceptance_criteria = issue.acceptance_criteria
                logger.info(f"Found {len(requirements)} requirements from issue #{issue_num}")
            except Exception as e:
                logger.warning(f"Could not fetch issue #{issue_num}: {e}")

        # Get PR diff and files
        diff = github_client.get_pr_diff(pr_number)
        files_changed = github_client.get_pr_files_changed(pr_number)
        file_paths = [fc.path for fc in files_changed]

        logger.info(f"PR has {len(files_changed)} changed files")

        # Parse CI artifacts
        ci_results = parse_ci_artifacts(artifact_dir)
        categorized_failures = categorize_failures(ci_results)

        logger.info(f"Parsed CI results: {len(categorized_failures.get('tests', []))} test failures, "
                   f"{len(categorized_failures.get('lint', []))} lint errors")

        # Analyze diff and changes
        pr_data = {
            "diff": diff,
            "files_changed": file_paths,
        }

        diff_analysis = analyze_pr_diff(diff, requirements, config)

        # Check requirement fulfillment
        requirements_fulfilled = {}
        if requirements:
            requirements_fulfilled = check_requirements_fulfillment(pr_data, requirements)

        # Parse diff for line comment positioning
        diff_data = _parse_diff_to_dict(diff, file_paths)

        # Generate line comments from CI failures
        line_comments = generate_line_comments(categorized_failures, diff_data)

        # Determine outcome
        outcome = determine_outcome(
            ci_results=ci_results,
            categorized_failures=categorized_failures,
            requirements_fulfilled=requirements_fulfilled,
            diff_analysis=diff_analysis,
        )

        # Build review output
        review = generate_review_with_line_comments(
            outcome=outcome,
            ci_results=ci_results,
            categorized_failures=categorized_failures,
            diff_analysis=diff_analysis,
            requirements_fulfilled=requirements_fulfilled,
            line_comments=line_comments,
            pr=pr,
            config=config,
        )

        logger.info(f"Review complete: approve={review.approve}, "
                   f"blocking_issues={len(review.blocking_issues)}, "
                   f"line_comments={len(review.line_comments)}")

        return review

    except Exception as e:
        logger.error(f"Failed to analyze PR #{pr_number}: {e}", exc_info=True)
        # Return a failure review
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
        github_client.close()


def determine_outcome(
    ci_results: Dict[str, Any],
    categorized_failures: Dict[str, List[Dict[str, Any]]],
    requirements_fulfilled: Dict[str, bool],
    diff_analysis: Dict[str, Any],
) -> Dict[str, Any]:
    """Determine review outcome based on CI results and analysis.

    Args:
        ci_results: Raw CI results from parse_ci_artifacts
        categorized_failures: Categorized failures from categorize_failures
        requirements_fulfilled: Requirement fulfillment mapping
        diff_analysis: Analysis from analyze_pr_diff

    Returns:
        Dictionary with outcome decision:
        {
            "approve": bool,
            "blocking_issues": List[str],
            "non_blocking_issues": List[str],
            "quality_score": float,
        }
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
        blocking_issues.append(f"High-severity security issues: {len(high_severity_security)} found")
        quality_score -= 3.0
    elif security_issues:
        non_blocking_issues.append(f"Security concerns: {len(security_issues)} issue(s) to review")
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


def generate_review_with_line_comments(
    outcome: Dict[str, Any],
    ci_results: Dict[str, Any],
    categorized_failures: Dict[str, List[Dict[str, Any]]],
    diff_analysis: Dict[str, Any],
    requirements_fulfilled: Dict[str, bool],
    line_comments: List[ReviewComment],
    pr: PullRequest,
    config: AgentConfig,
) -> ReviewOutput:
    """Generate comprehensive review output with summary and line comments.

    Args:
        outcome: Outcome from determine_outcome
        ci_results: Raw CI results
        categorized_failures: Categorized failures
        diff_analysis: Diff analysis results
        requirements_fulfilled: Requirements fulfillment mapping
        line_comments: Generated line comments
        pr: PullRequest object
        config: Agent configuration

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
    requirements_fulfilled_list = list(requirements_fulfilled.values()) if requirements_fulfilled else []

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


def post_review_idempotent(
    pr_number: int,
    review: ReviewOutput,
    config: AgentConfig,
) -> None:
    """Post review to GitHub PR in an idempotent way.

    Uses GitHub client methods to:
    - Dismiss old bot reviews
    - Post new review with appropriate event (APPROVE/REQUEST_CHANGES/COMMENT)
    - Update summary comment

    Args:
        pr_number: GitHub PR number
        review: ReviewOutput to post
        config: Agent configuration
    """
    github_client = GitHubClient(config)

    try:
        # Dismiss old bot reviews to avoid clutter
        github_client.dismiss_old_bot_reviews(pr_number)

        # Determine review event
        # Note: GitHub Actions bots cannot APPROVE PRs, so we use COMMENT instead
        if review.blocking_issues:
            event = "REQUEST_CHANGES"
        else:
            event = "COMMENT"

        # Post review
        github_client.post_review(pr_number, review, event)

        # Also post/update summary comment
        summary_text = _format_summary_comment(review)
        github_client.post_summary_comment_idempotent(pr_number, summary_text)

        logger.info(f"Posted review to PR #{pr_number} with event: {event}")

    except Exception as e:
        logger.error(f"Failed to post review to PR #{pr_number}: {e}", exc_info=True)
        raise

    finally:
        github_client.close()


def _parse_diff_to_dict(diff: str, file_paths: List[str]) -> Dict[str, Any]:
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


def _extract_iteration_from_labels(labels: List[str]) -> int:
    """Extract iteration number from PR labels.

    Args:
        labels: List of label names

    Returns:
        Iteration number (default 1)
    """
    import re

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


@click.group()
def cli():
    """AI Reviewer Agent for automated code review."""
    pass


@cli.command()
@click.option("--pr-number", required=True, type=int, help="Pull request number")
@click.option("--issue-number", type=int, help="Associated issue number")
@click.option("--artifact-dir", required=True, help="Directory with CI artifacts")
@click.option("--output", required=True, help="Output JSON file for review results")
@click.option("--post-review", is_flag=True, help="Post review to GitHub")
def review(
    pr_number: int,
    issue_number: Optional[int],
    artifact_dir: str,
    output: str,
    post_review: bool,
):
    """Analyze a pull request and generate review.

    Example:
        reviewer review --pr-number 123 --artifact-dir ./artifacts --output review.json --post-review
    """
    try:
        config = load_config()

        logger.info(f"Starting review of PR #{pr_number}")

        # Analyze PR
        review_output = analyze_pr(pr_number, issue_number, artifact_dir, config)

        # Save to output file
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(review_output.model_dump(mode="json"), f, indent=2, default=str)

        logger.info(f"Review saved to {output}")

        # Post to GitHub if requested
        if post_review:
            logger.info("Posting review to GitHub...")
            post_review_idempotent(pr_number, review_output, config)

        # Exit with appropriate code
        if review_output.approve:
            logger.info("Review complete: APPROVED")
            sys.exit(0)
        else:
            logger.info("Review complete: CHANGES REQUESTED")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Review failed: {e}", exc_info=True)
        sys.exit(1)


@cli.command()
@click.option("--review-file", required=True, help="Path to review JSON file")
@click.option("--pr-number", required=True, type=int, help="Pull request number")
def post(review_file: str, pr_number: int):
    """Post a saved review to GitHub.

    Example:
        reviewer post --review-file review.json --pr-number 123
    """
    try:
        config = load_config()

        # Load review from file
        with open(review_file, "r") as f:
            review_data = json.load(f)

        review_output = ReviewOutput.model_validate(review_data)

        # Post to GitHub
        post_review_idempotent(pr_number, review_output, config)

        logger.info("Review posted successfully")
        sys.exit(0)

    except Exception as e:
        logger.error(f"Failed to post review: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
