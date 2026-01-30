"""Basic smoke tests for ReviewerOrchestrator."""

from unittest.mock import MagicMock, patch

import pytest

from src.common.config import AgentConfig
from src.common.models import PullRequest, ReviewOutput
from src.reviewer_agent.orchestrator import ReviewerOrchestrator


@pytest.fixture
def mock_config():
    """Mock configuration."""
    return AgentConfig(
        github_repository="owner/repo",
        github_token="test_token",
        llm_provider="openai",
        openai_api_key="test_key",
    )


def test_analyze_pull_request_success(mock_config):
    """Test successful PR analysis."""
    orchestrator = ReviewerOrchestrator(mock_config)

    # Mock GitHub client
    with patch("src.reviewer_agent.orchestrator.GitHubClient") as mock_github_client_cls:
        mock_client = MagicMock()
        mock_github_client_cls.return_value = mock_client

        # Setup mocks
        from datetime import datetime

        mock_pr = PullRequest(
            number=123,
            title="Test PR",
            body="Test description",
            state="open",
            head_branch="test-branch",
            base_branch="main",
            labels=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            html_url="https://github.com/owner/repo/pull/123",
            issue_number=None,
        )
        mock_client.fetch_pull_request.return_value = mock_pr
        mock_client.get_pr_diff.return_value = "diff content"
        mock_client.get_pr_files_changed.return_value = []

        # Mock CI parsing
        with patch("src.reviewer_agent.orchestrator.parse_ci_artifacts") as mock_parse:
            with patch("src.reviewer_agent.orchestrator.categorize_failures") as mock_categorize:
                with patch("src.reviewer_agent.orchestrator.analyze_pr_diff") as mock_diff:
                    with patch(
                        "src.reviewer_agent.orchestrator.check_requirements_fulfillment"
                    ) as mock_req:
                        with patch(
                            "src.reviewer_agent.orchestrator.generate_line_comments"
                        ) as mock_comments:
                            mock_parse.return_value = {}
                            mock_categorize.return_value = {}
                            mock_diff.return_value = {
                                "summary": "Test summary",
                                "potential_issues": [],
                            }
                            mock_req.return_value = {}
                            mock_comments.return_value = []

                            # Execute
                            result = orchestrator.analyze_pull_request(123, None)

                            # Verify
                            assert isinstance(result, ReviewOutput)
                            assert result.iteration == 1


def test_review_pull_request_without_posting(mock_config):
    """Test review without posting to GitHub."""
    orchestrator = ReviewerOrchestrator(mock_config)

    with patch.object(orchestrator, "analyze_pull_request") as mock_analyze:
        mock_analyze.return_value = ReviewOutput(
            approve=True,
            summary="Looks good",
            blocking_issues=[],
            non_blocking_issues=[],
            line_comments=[],
            requirements_fulfilled=[],
            overall_quality_score=8.0,
        )

        result = orchestrator.review_pull_request(123, None, post_review=False)

        assert result.success is True
        assert result.decision == "approve"
        assert result.issues_count == 0


def test_review_pull_request_posting_failure_preserves_analysis(mock_config):
    """Test that analysis results are preserved when posting fails."""
    orchestrator = ReviewerOrchestrator(mock_config)

    mock_review = ReviewOutput(
        approve=False,
        summary="Needs work",
        blocking_issues=["Test failed"],
        non_blocking_issues=[],
        line_comments=[],
        requirements_fulfilled=[],
        overall_quality_score=5.0,
    )

    with patch.object(orchestrator, "analyze_pull_request") as mock_analyze:
        mock_analyze.return_value = mock_review

        with patch.object(orchestrator, "post_review") as mock_post:
            mock_post.side_effect = Exception("GitHub API error")

            result = orchestrator.review_pull_request(123, None, post_review=True)

            assert result.success is False
            assert "posting failed" in result.error.lower()
            assert result.review_output is not None
            assert result.review_output.summary == "Needs work"
