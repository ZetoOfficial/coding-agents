"""GitHub client wrapper using PyGithub for GitHub API operations."""

import logging
import re
from typing import List, Optional, Tuple
from datetime import datetime

from github import Github, GithubException, RateLimitExceededException
from github.Repository import Repository
from github.Issue import Issue as GithubIssue
from github.PullRequest import PullRequest as GithubPullRequest
from github.PullRequestReview import PullRequestReview
from github.PullRequestComment import PullRequestComment

from src.common.config import AgentConfig
from src.common.models import (
    Issue,
    IssueLabel,
    PullRequest,
    FileChange,
    ReviewOutput,
)

logger = logging.getLogger(__name__)


class GitHubClient:
    """GitHub API client wrapper with helper methods for SDLC operations."""

    AI_SUMMARY_MARKER = "<!-- AI-SUMMARY-MARKER -->"
    BOT_IDENTIFIER = "github-actions[bot]"

    def __init__(self, config: AgentConfig) -> None:
        """Initialize GitHub client with token from config.

        Args:
            config: Agent configuration containing GitHub token and repo info
        """
        self.config = config
        self.github = Github(config.get_github_token())
        self.repo: Repository = self.github.get_repo(config.github_repository)
        logger.info(f"Initialized GitHub client for repository: {config.github_repository}")

    def _handle_rate_limit(self) -> None:
        """Check and log rate limit status."""
        try:
            rate_limit = self.github.get_rate_limit()
            core = rate_limit.core
            logger.debug(
                f"GitHub API rate limit: {core.remaining}/{core.limit} "
                f"(resets at {core.reset})"
            )
            if core.remaining < 100:
                logger.warning(
                    f"Low GitHub API rate limit: {core.remaining} requests remaining"
                )
        except Exception as e:
            logger.warning(f"Failed to check rate limit: {e}")

    # ============================================================================
    # Issue Operations
    # ============================================================================

    def fetch_issue(self, issue_number: int) -> Issue:
        """Fetch issue details and convert to our Pydantic model.

        Args:
            issue_number: GitHub issue number

        Returns:
            Issue model with all details

        Raises:
            GithubException: If issue not found or API error occurs
        """
        try:
            self._handle_rate_limit()
            gh_issue: GithubIssue = self.repo.get_issue(issue_number)

            labels = [
                IssueLabel(
                    name=label.name,
                    color=label.color,
                    description=label.description or "",
                )
                for label in gh_issue.labels
            ]

            issue = Issue(
                number=gh_issue.number,
                title=gh_issue.title,
                body=gh_issue.body or "",
                state=gh_issue.state,  # type: ignore
                labels=labels,
                created_at=gh_issue.created_at,
                updated_at=gh_issue.updated_at,
                user=gh_issue.user.login if gh_issue.user else "unknown",
                html_url=gh_issue.html_url,
            )

            logger.info(f"Fetched issue #{issue_number}: {issue.title}")
            return issue

        except GithubException as e:
            logger.error(f"Failed to fetch issue #{issue_number}: {e}")
            raise

    def add_issue_comment(self, issue_number: int, comment: str) -> None:
        """Add a comment to an issue.

        Args:
            issue_number: GitHub issue number
            comment: Comment text to add

        Raises:
            GithubException: If API error occurs
        """
        try:
            self._handle_rate_limit()
            gh_issue: GithubIssue = self.repo.get_issue(issue_number)
            gh_issue.create_comment(comment)
            logger.info(f"Added comment to issue #{issue_number}")

        except GithubException as e:
            logger.error(f"Failed to add comment to issue #{issue_number}: {e}")
            raise

    def update_issue_labels(
        self,
        issue_number: int,
        labels_to_add: List[str],
        labels_to_remove: List[str],
    ) -> None:
        """Update labels on an issue.

        Args:
            issue_number: GitHub issue number
            labels_to_add: List of label names to add
            labels_to_remove: List of label names to remove

        Raises:
            GithubException: If API error occurs
        """
        try:
            self._handle_rate_limit()
            gh_issue: GithubIssue = self.repo.get_issue(issue_number)

            # Get current labels
            current_labels = [label.name for label in gh_issue.labels]

            # Calculate new label set
            new_labels = set(current_labels)
            new_labels.update(labels_to_add)
            new_labels.difference_update(labels_to_remove)

            # Update labels
            gh_issue.set_labels(*list(new_labels))

            logger.info(
                f"Updated labels on issue #{issue_number}: "
                f"added={labels_to_add}, removed={labels_to_remove}"
            )

        except GithubException as e:
            logger.error(f"Failed to update labels on issue #{issue_number}: {e}")
            raise

    # ============================================================================
    # PR Operations
    # ============================================================================

    def create_pull_request(
        self,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str,
        issue_number: int,
    ) -> PullRequest:
        """Create a pull request.

        Args:
            title: PR title
            body: PR description
            head_branch: Source branch
            base_branch: Target branch
            issue_number: Associated issue number

        Returns:
            PullRequest model

        Raises:
            GithubException: If PR creation fails
        """
        try:
            self._handle_rate_limit()

            # Add issue reference to body
            pr_body = f"{body}\n\nCloses #{issue_number}"

            gh_pr: GithubPullRequest = self.repo.create_pull(
                title=title,
                body=pr_body,
                head=head_branch,
                base=base_branch,
            )

            # Add iteration label
            gh_pr.add_to_labels("iteration-1")

            pr = self._convert_pr_to_model(gh_pr, issue_number)

            logger.info(
                f"Created PR #{pr.number}: {title} "
                f"({head_branch} -> {base_branch})"
            )
            return pr

        except GithubException as e:
            logger.error(f"Failed to create PR: {e}")
            raise

    def fetch_pull_request(self, pr_number: int) -> PullRequest:
        """Fetch pull request details.

        Args:
            pr_number: GitHub PR number

        Returns:
            PullRequest model

        Raises:
            GithubException: If PR not found or API error occurs
        """
        try:
            self._handle_rate_limit()
            gh_pr: GithubPullRequest = self.repo.get_pull(pr_number)
            pr = self._convert_pr_to_model(gh_pr)

            logger.info(f"Fetched PR #{pr_number}: {pr.title}")
            return pr

        except GithubException as e:
            logger.error(f"Failed to fetch PR #{pr_number}: {e}")
            raise

    def get_pr_diff(self, pr_number: int) -> str:
        """Get the unified diff for a pull request.

        Args:
            pr_number: GitHub PR number

        Returns:
            Unified diff string

        Raises:
            GithubException: If API error occurs
        """
        try:
            self._handle_rate_limit()
            gh_pr: GithubPullRequest = self.repo.get_pull(pr_number)

            # Get diff using the diff URL
            import requests

            headers = {
                "Authorization": f"token {self.config.get_github_token()}",
                "Accept": "application/vnd.github.v3.diff",
            }
            response = requests.get(gh_pr.url, headers=headers)
            response.raise_for_status()

            diff_content = response.text
            logger.info(f"Retrieved diff for PR #{pr_number} ({len(diff_content)} chars)")
            return diff_content

        except Exception as e:
            logger.error(f"Failed to get diff for PR #{pr_number}: {e}")
            raise

    def get_pr_files_changed(self, pr_number: int) -> List[FileChange]:
        """Get list of files changed in a pull request.

        Args:
            pr_number: GitHub PR number

        Returns:
            List of FileChange models

        Raises:
            GithubException: If API error occurs
        """
        try:
            self._handle_rate_limit()
            gh_pr: GithubPullRequest = self.repo.get_pull(pr_number)

            files = []
            for file in gh_pr.get_files():
                # Map GitHub status to our change_type
                change_type_map = {
                    "added": "added",
                    "modified": "modified",
                    "removed": "deleted",
                    "renamed": "modified",
                }
                change_type = change_type_map.get(file.status, "modified")  # type: ignore

                files.append(
                    FileChange(
                        path=file.filename,
                        change_type=change_type,  # type: ignore
                        additions=file.additions,
                        deletions=file.deletions,
                        patch=file.patch,
                    )
                )

            logger.info(f"Retrieved {len(files)} changed files for PR #{pr_number}")
            return files

        except GithubException as e:
            logger.error(f"Failed to get changed files for PR #{pr_number}: {e}")
            raise

    # ============================================================================
    # Review Operations
    # ============================================================================

    def post_review(
        self,
        pr_number: int,
        review_data: ReviewOutput,
        event: str = "COMMENT",
    ) -> None:
        """Post a review on a pull request.

        Args:
            pr_number: GitHub PR number
            review_data: ReviewOutput model with review details
            event: Review event type (APPROVE, REQUEST_CHANGES, COMMENT)

        Raises:
            GithubException: If API error occurs
        """
        try:
            self._handle_rate_limit()
            gh_pr: GithubPullRequest = self.repo.get_pull(pr_number)

            # Build review body
            body_parts = [f"## AI Code Review - Iteration {review_data.iteration}\n"]

            body_parts.append(f"**Summary:** {review_data.summary}\n")
            body_parts.append(
                f"**Quality Score:** {review_data.overall_quality_score}/10\n"
            )

            if review_data.blocking_issues:
                body_parts.append("\n### Blocking Issues")
                for issue in review_data.blocking_issues:
                    body_parts.append(f"- {issue}")

            if review_data.non_blocking_issues:
                body_parts.append("\n### Non-Blocking Issues")
                for issue in review_data.non_blocking_issues:
                    body_parts.append(f"- {issue}")

            if review_data.ci_summary:
                body_parts.append("\n### CI Summary")
                for key, value in review_data.ci_summary.items():
                    body_parts.append(f"- **{key}**: {value}")

            body = "\n".join(body_parts)

            # Post review comments on specific lines
            comments = []
            for line_comment in review_data.line_comments:
                if line_comment.path and line_comment.line:
                    comments.append(
                        {
                            "path": line_comment.path,
                            "line": line_comment.line,
                            "body": line_comment.body,
                        }
                    )

            # Create review
            if comments:
                gh_pr.create_review(
                    body=body,
                    event=event,
                    comments=comments,
                )
            else:
                gh_pr.create_review(body=body, event=event)

            logger.info(f"Posted review on PR #{pr_number} with event: {event}")

        except GithubException as e:
            logger.error(f"Failed to post review on PR #{pr_number}: {e}")
            raise

    def post_summary_comment_idempotent(
        self,
        pr_number: int,
        summary: str,
    ) -> None:
        """Post or update a summary comment on a PR (idempotent).

        Uses HTML marker to identify and update existing summary comments.

        Args:
            pr_number: GitHub PR number
            summary: Summary text to post

        Raises:
            GithubException: If API error occurs
        """
        try:
            self._handle_rate_limit()
            gh_pr: GithubPullRequest = self.repo.get_pull(pr_number)

            # Build comment with marker
            comment_body = f"{self.AI_SUMMARY_MARKER}\n\n{summary}"

            # Find existing summary comment
            existing_comment = None
            for comment in gh_pr.get_issue_comments():
                if (
                    comment.user.login == self.BOT_IDENTIFIER
                    and self.AI_SUMMARY_MARKER in (comment.body or "")
                ):
                    existing_comment = comment
                    break

            # Update or create comment
            if existing_comment:
                existing_comment.edit(comment_body)
                logger.info(f"Updated summary comment on PR #{pr_number}")
            else:
                gh_pr.create_issue_comment(comment_body)
                logger.info(f"Created summary comment on PR #{pr_number}")

        except GithubException as e:
            logger.error(f"Failed to post summary comment on PR #{pr_number}: {e}")
            raise

    def dismiss_old_bot_reviews(self, pr_number: int) -> None:
        """Dismiss old bot reviews on a PR.

        Args:
            pr_number: GitHub PR number

        Raises:
            GithubException: If API error occurs
        """
        try:
            self._handle_rate_limit()
            gh_pr: GithubPullRequest = self.repo.get_pull(pr_number)

            dismissed_count = 0
            for review in gh_pr.get_reviews():
                # Only dismiss bot reviews that are not already dismissed
                if (
                    review.user.login == self.BOT_IDENTIFIER
                    and review.state in ["APPROVED", "CHANGES_REQUESTED"]
                ):
                    try:
                        review.dismiss("Superseded by newer review")
                        dismissed_count += 1
                    except GithubException as e:
                        logger.warning(f"Failed to dismiss review {review.id}: {e}")

            if dismissed_count > 0:
                logger.info(f"Dismissed {dismissed_count} old reviews on PR #{pr_number}")

        except GithubException as e:
            logger.error(f"Failed to dismiss old reviews on PR #{pr_number}: {e}")
            raise

    def parse_review_feedback(self, pr_number: int) -> List[str]:
        """Extract reviewer comments from PR reviews and comments.

        Args:
            pr_number: GitHub PR number

        Returns:
            List of feedback strings from reviewers

        Raises:
            GithubException: If API error occurs
        """
        try:
            self._handle_rate_limit()
            gh_pr: GithubPullRequest = self.repo.get_pull(pr_number)

            feedback = []

            # Get review comments
            for review in gh_pr.get_reviews():
                # Skip bot reviews
                if review.user.login == self.BOT_IDENTIFIER:
                    continue

                if review.body:
                    feedback.append(
                        f"[Review by {review.user.login}] {review.body}"
                    )

            # Get line comments
            for comment in gh_pr.get_review_comments():
                # Skip bot comments
                if comment.user.login == self.BOT_IDENTIFIER:
                    continue

                feedback.append(
                    f"[Comment by {comment.user.login} on {comment.path}:{comment.line}] "
                    f"{comment.body}"
                )

            # Get general issue comments
            for comment in gh_pr.get_issue_comments():
                # Skip bot comments and comments with AI marker
                if (
                    comment.user.login == self.BOT_IDENTIFIER
                    or self.AI_SUMMARY_MARKER in (comment.body or "")
                ):
                    continue

                feedback.append(
                    f"[Comment by {comment.user.login}] {comment.body}"
                )

            logger.info(f"Parsed {len(feedback)} feedback items from PR #{pr_number}")
            return feedback

        except GithubException as e:
            logger.error(f"Failed to parse feedback for PR #{pr_number}: {e}")
            raise

    # ============================================================================
    # Label Operations
    # ============================================================================

    def get_iteration_from_labels(self, labels: List[str]) -> int:
        """Extract iteration number from label names.

        Looks for labels matching pattern "iteration-N".

        Args:
            labels: List of label names

        Returns:
            Iteration number (defaults to 1 if not found)
        """
        for label in labels:
            match = re.match(r"iteration-(\d+)", label.lower())
            if match:
                iteration = int(match.group(1))
                logger.debug(f"Found iteration label: {iteration}")
                return iteration

        logger.debug("No iteration label found, defaulting to 1")
        return 1

    def check_iteration_limit(
        self,
        pr_number: int,
        max_iterations: int,
    ) -> Tuple[bool, int]:
        """Check if PR has exceeded iteration limit.

        Args:
            pr_number: GitHub PR number
            max_iterations: Maximum allowed iterations

        Returns:
            Tuple of (exceeded: bool, current_iteration: int)

        Raises:
            GithubException: If API error occurs
        """
        try:
            self._handle_rate_limit()
            gh_pr: GithubPullRequest = self.repo.get_pull(pr_number)

            label_names = [label.name for label in gh_pr.labels]
            current_iteration = self.get_iteration_from_labels(label_names)

            exceeded = current_iteration > max_iterations

            logger.info(
                f"PR #{pr_number} iteration check: {current_iteration}/{max_iterations} "
                f"(exceeded: {exceeded})"
            )

            return exceeded, current_iteration

        except GithubException as e:
            logger.error(f"Failed to check iteration limit for PR #{pr_number}: {e}")
            raise

    # ============================================================================
    # Repository Operations
    # ============================================================================

    def get_file_content(self, file_path: str, ref: str = "main") -> str:
        """Get file content from repository.

        Args:
            file_path: Path to file in repository
            ref: Git reference (branch, tag, commit SHA)

        Returns:
            File content as string

        Raises:
            GithubException: If file not found or API error occurs
        """
        try:
            self._handle_rate_limit()
            contents = self.repo.get_contents(file_path, ref=ref)

            # Handle file content
            if isinstance(contents, list):
                raise ValueError(f"Path {file_path} is a directory, not a file")

            content = contents.decoded_content.decode("utf-8")
            logger.info(f"Retrieved content for file: {file_path} (ref: {ref})")
            return content

        except GithubException as e:
            logger.error(f"Failed to get content for {file_path} (ref: {ref}): {e}")
            raise

    def list_directory_contents(self, path: str = "") -> List[str]:
        """List contents of a directory in the repository.

        Args:
            path: Directory path (empty string for root)

        Returns:
            List of file/directory paths

        Raises:
            GithubException: If API error occurs
        """
        try:
            self._handle_rate_limit()
            contents = self.repo.get_contents(path)

            # Handle both single file and directory listings
            if not isinstance(contents, list):
                contents = [contents]

            paths = [item.path for item in contents]
            logger.info(f"Listed {len(paths)} items in directory: {path or '/'}")
            return paths

        except GithubException as e:
            logger.error(f"Failed to list directory contents for {path}: {e}")
            raise

    # ============================================================================
    # Helper Methods
    # ============================================================================

    def _convert_pr_to_model(
        self,
        gh_pr: GithubPullRequest,
        issue_number: Optional[int] = None,
    ) -> PullRequest:
        """Convert PyGithub PullRequest to our Pydantic model.

        Args:
            gh_pr: PyGithub PullRequest object
            issue_number: Optional issue number to associate

        Returns:
            PullRequest model
        """
        labels = [
            IssueLabel(
                name=label.name,
                color=label.color,
                description=label.description or "",
            )
            for label in gh_pr.labels
        ]

        # Determine state
        if gh_pr.merged:
            state = "merged"
        else:
            state = gh_pr.state  # type: ignore

        # Extract issue number from body if not provided
        if issue_number is None and gh_pr.body:
            match = re.search(r"Closes #(\d+)", gh_pr.body)
            if match:
                issue_number = int(match.group(1))

        return PullRequest(
            number=gh_pr.number,
            title=gh_pr.title,
            body=gh_pr.body or "",
            state=state,  # type: ignore
            head_branch=gh_pr.head.ref,
            base_branch=gh_pr.base.ref,
            labels=labels,
            created_at=gh_pr.created_at,
            updated_at=gh_pr.updated_at,
            html_url=gh_pr.html_url,
            mergeable=gh_pr.mergeable,
            issue_number=issue_number,
        )

    def close(self) -> None:
        """Close the GitHub client and cleanup resources."""
        if hasattr(self, "github"):
            self.github.close()
            logger.info("Closed GitHub client")
