"""RQ task definitions for async agent processing."""

import logging
import tempfile
from pathlib import Path
from typing import Dict, Any

from rq import get_current_job
from rq.job import Job

from src.common.config import AgentConfig
from src.webhook_server.github_app_auth import GitHubAppAuth

logger = logging.getLogger(__name__)


def process_issue_task(
    issue_number: int,
    repository: str,
    installation_id: int,
    config_dict: Dict[str, Any],
    force: bool = False
) -> Dict[str, Any]:
    """RQ task for processing GitHub issues.

    Args:
        issue_number: Issue number to process
        repository: Repository full name (owner/repo)
        installation_id: GitHub App installation ID
        config_dict: Configuration dictionary
        force: Force reprocessing even if already processed

    Returns:
        Result dictionary with success status and details
    """
    job = get_current_job()
    logger.info(f"[Job {job.id}] Starting issue processing: #{issue_number} in {repository}")

    try:
        # Rebuild config from dict
        config = _build_config_from_dict(config_dict, repository, installation_id)

        # Import here to avoid circular dependencies
        from src.code_agent.orchestrator import CodeAgentOrchestrator

        # Create orchestrator
        orchestrator = CodeAgentOrchestrator(config)

        # Create temporary workspace for repository
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = str(Path(tmpdir) / "repo")

            # Process the issue
            result = orchestrator.process_issue(
                issue_number=issue_number,
                repo_path=repo_path,
                force=force
            )

            logger.info(
                f"[Job {job.id}] Issue processing completed: "
                f"success={result.success}, pr_number={result.pr_number}"
            )

            return {
                "success": result.success,
                "pr_number": result.pr_number,
                "branch_name": result.branch_name,
                "error": result.error,
                "issue_number": issue_number,
                "repository": repository
            }

    except Exception as e:
        logger.error(f"[Job {job.id}] Issue processing failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "issue_number": issue_number,
            "repository": repository
        }


def apply_feedback_task(
    pr_number: int,
    repository: str,
    installation_id: int,
    config_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """RQ task for applying reviewer feedback to PRs.

    Args:
        pr_number: Pull request number
        repository: Repository full name (owner/repo)
        installation_id: GitHub App installation ID
        config_dict: Configuration dictionary

    Returns:
        Result dictionary with success status and details
    """
    job = get_current_job()
    logger.info(f"[Job {job.id}] Starting feedback application: PR #{pr_number} in {repository}")

    try:
        # Rebuild config from dict
        config = _build_config_from_dict(config_dict, repository, installation_id)

        # Import here to avoid circular dependencies
        from src.code_agent.orchestrator import CodeAgentOrchestrator

        # Create orchestrator
        orchestrator = CodeAgentOrchestrator(config)

        # Create temporary workspace
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = str(Path(tmpdir) / "repo")

            # Apply feedback
            result = orchestrator.apply_feedback(
                pr_number=pr_number,
                repo_path=repo_path
            )

            logger.info(
                f"[Job {job.id}] Feedback application completed: "
                f"success={result.success}, iteration={result.iteration}"
            )

            return {
                "success": result.success,
                "iteration": result.iteration,
                "fixes_applied": result.fixes_applied,
                "error": result.error,
                "pr_number": pr_number,
                "repository": repository
            }

    except Exception as e:
        logger.error(f"[Job {job.id}] Feedback application failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "pr_number": pr_number,
            "repository": repository
        }


def review_pr_task(
    pr_number: int,
    repository: str,
    installation_id: int,
    config_dict: Dict[str, Any],
    artifacts_url: str
) -> Dict[str, Any]:
    """RQ task for AI-powered PR review.

    Args:
        pr_number: Pull request number
        repository: Repository full name (owner/repo)
        installation_id: GitHub App installation ID
        config_dict: Configuration dictionary
        artifacts_url: URL to CI artifacts

    Returns:
        Result dictionary with success status and details
    """
    job = get_current_job()
    logger.info(f"[Job {job.id}] Starting PR review: #{pr_number} in {repository}")

    try:
        # Rebuild config from dict
        config = _build_config_from_dict(config_dict, repository, installation_id)

        # Import here to avoid circular dependencies
        from src.reviewer_agent.orchestrator import ReviewerOrchestrator

        # Create orchestrator
        orchestrator = ReviewerOrchestrator(config)

        # Download artifacts (implementation depends on CI system)
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir) / "artifacts"
            artifact_dir.mkdir()

            # TODO: Download artifacts from artifacts_url
            # For now, skip artifact download if URL is empty
            if artifacts_url:
                logger.info(f"Downloading artifacts from {artifacts_url}")
                # _download_artifacts(artifacts_url, artifact_dir)

            # Perform review
            result = orchestrator.review_pull_request(
                pr_number=pr_number,
                artifact_dir=str(artifact_dir) if artifacts_url else None,
                post_review=True
            )

            logger.info(
                f"[Job {job.id}] PR review completed: "
                f"success={result.success}, decision={result.decision}"
            )

            return {
                "success": result.success,
                "decision": result.decision,
                "issues_found": result.issues_count,
                "error": result.error,
                "pr_number": pr_number,
                "repository": repository
            }

    except Exception as e:
        logger.error(f"[Job {job.id}] PR review failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "pr_number": pr_number,
            "repository": repository
        }


def _build_config_from_dict(
    config_dict: Dict[str, Any],
    repository: str,
    installation_id: int
) -> AgentConfig:
    """Build AgentConfig with GitHub App token from dictionary.

    Args:
        config_dict: Configuration as dictionary
        repository: Repository full name
        installation_id: GitHub App installation ID

    Returns:
        AgentConfig instance with installation token
    """
    # Update repository and installation ID
    config_dict["github_repository"] = repository
    config_dict["github_app_installation_id"] = installation_id

    # Create config
    config = AgentConfig(**config_dict)

    # Get installation token and inject it
    auth = GitHubAppAuth(config)
    token = auth.get_installation_token()

    # Create a new config dict with token
    config_with_token = config_dict.copy()
    config_with_token["github_token"] = token
    config_with_token["github_repository"] = repository

    return AgentConfig(**config_with_token)
