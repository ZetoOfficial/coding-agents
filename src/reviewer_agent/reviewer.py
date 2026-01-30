"""Main reviewer agent CLI for automated PR review.

This module provides the CLI interface for the AI reviewer agent.
All business logic has been moved to orchestrator.py.
"""

import json
import logging
import sys
from pathlib import Path

import click

from src.common.config import load_config
from src.common.models import ReviewOutput
from src.reviewer_agent.orchestrator import ReviewerOrchestrator

logger = logging.getLogger(__name__)


@click.group()
def cli():
    """AI Reviewer Agent for automated code review."""
    pass


@cli.command()
@click.option("--pr-number", required=True, type=int, help="Pull request number")
@click.option("--artifact-dir", required=True, help="Directory with CI artifacts")
@click.option("--output", required=True, help="Output JSON file for review results")
@click.option("--post-review", is_flag=True, help="Post review to GitHub")
def review(
    pr_number: int,
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
        orchestrator = ReviewerOrchestrator(config)

        logger.info(f"Starting review of PR #{pr_number}")

        # Analyze PR
        review_output = orchestrator.analyze_pull_request(
            pr_number=pr_number, artifact_dir=artifact_dir
        )

        # Save to output file
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(review_output.model_dump(mode="json"), f, indent=2, default=str)

        logger.info(f"Review saved to {output}")

        # Post to GitHub if requested
        if post_review:
            logger.info("Posting review to GitHub...")
            orchestrator.post_review(pr_number, review_output)

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
        orchestrator = ReviewerOrchestrator(config)

        # Load review from file
        with open(review_file) as f:
            review_data = json.load(f)

        review_output = ReviewOutput.model_validate(review_data)

        # Post to GitHub
        orchestrator.post_review(pr_number, review_output)

        logger.info("Review posted successfully")
        sys.exit(0)

    except Exception as e:
        logger.error(f"Failed to post review: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
