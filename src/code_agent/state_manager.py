"""State management for tracking agent iterations and detecting stuck loops."""

import json
import logging
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime
from difflib import SequenceMatcher

from src.common.models import AgentState

logger = logging.getLogger(__name__)


class StateManager:
    """Manages agent state persistence and stuck loop detection."""

    STATE_DIR = Path(".agent-state")
    SIMILARITY_THRESHOLD = 0.7  # 70% similarity to consider errors as repeating
    STUCK_CHECK_WINDOW = 3  # Check last 3 reviews for stuck detection

    def __init__(self, state_dir: Optional[Path] = None) -> None:
        """Initialize state manager.

        Args:
            state_dir: Optional custom directory for state files (defaults to .agent-state/)
        """
        self.state_dir = state_dir or self.STATE_DIR
        self._ensure_state_directory()
        logger.info(f"Initialized StateManager with directory: {self.state_dir}")

    def _ensure_state_directory(self) -> None:
        """Create state directory if it doesn't exist."""
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"State directory ready: {self.state_dir}")
        except Exception as e:
            logger.error(f"Failed to create state directory: {e}")
            raise

    def _get_state_file_path(self, issue_number: int) -> Path:
        """Get path to state file for given issue number.

        Args:
            issue_number: GitHub issue number

        Returns:
            Path to state file
        """
        return self.state_dir / f"issue-{issue_number}.json"

    def save_state(self, state: AgentState) -> None:
        """Save agent state to JSON file.

        Updates the updated_at timestamp automatically before saving.

        Args:
            state: AgentState to save

        Raises:
            IOError: If file write fails
        """
        try:
            # Update timestamp
            state.updated_at = datetime.utcnow()

            file_path = self._get_state_file_path(state.issue_number)

            # Convert to dict and handle datetime serialization
            state_dict = state.model_dump(mode="json")

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(state_dict, f, indent=2, ensure_ascii=False)

            logger.info(
                f"Saved state for issue #{state.issue_number} "
                f"(iteration {state.iteration}, status: {state.status})"
            )

        except Exception as e:
            logger.error(f"Failed to save state for issue #{state.issue_number}: {e}")
            raise

    def load_state(self, issue_number: int) -> Optional[AgentState]:
        """Load agent state from JSON file.

        Args:
            issue_number: GitHub issue number

        Returns:
            AgentState if file exists, None otherwise

        Raises:
            ValueError: If JSON is invalid or doesn't match AgentState schema
        """
        try:
            file_path = self._get_state_file_path(issue_number)

            if not file_path.exists():
                logger.debug(f"No state file found for issue #{issue_number}")
                return None

            with open(file_path, "r", encoding="utf-8") as f:
                state_dict = json.load(f)

            # Parse with Pydantic model
            state = AgentState(**state_dict)

            logger.info(
                f"Loaded state for issue #{issue_number} "
                f"(iteration {state.iteration}, status: {state.status})"
            )
            return state

        except FileNotFoundError:
            logger.debug(f"State file not found for issue #{issue_number}")
            return None

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in state file for issue #{issue_number}: {e}")
            raise ValueError(f"Corrupted state file: {e}") from e

        except Exception as e:
            logger.error(f"Failed to load state for issue #{issue_number}: {e}")
            raise

    def update_state(self, issue_number: int, **updates) -> AgentState:
        """Update specific fields in agent state.

        Loads existing state, applies updates, and saves back to file.
        If no state exists, creates a new one.

        Args:
            issue_number: GitHub issue number
            **updates: Keyword arguments for fields to update

        Returns:
            Updated AgentState

        Raises:
            ValueError: If updates contain invalid fields
        """
        try:
            # Load existing state or create new one
            state = self.load_state(issue_number)

            if state is None:
                logger.info(f"Creating new state for issue #{issue_number}")
                state = AgentState(issue_number=issue_number)

            # Apply updates
            for key, value in updates.items():
                if not hasattr(state, key):
                    raise ValueError(f"Invalid field for AgentState: {key}")

                setattr(state, key, value)
                logger.debug(f"Updated field '{key}' for issue #{issue_number}")

            # Save updated state
            self.save_state(state)

            return state

        except Exception as e:
            logger.error(f"Failed to update state for issue #{issue_number}: {e}")
            raise

    def detect_stuck_loop(self, state: AgentState) -> Tuple[bool, str]:
        """Detect if agent is stuck in a loop with repeating errors.

        Analyzes the last N review histories to check if similar errors
        are appearing repeatedly, indicating the agent is stuck.

        Args:
            state: Current AgentState to analyze

        Returns:
            Tuple of (is_stuck: bool, reason: str)
            - is_stuck: True if stuck loop detected
            - reason: Human-readable explanation of why stuck
        """
        try:
            # Need at least STUCK_CHECK_WINDOW reviews to detect pattern
            if len(state.review_history) < self.STUCK_CHECK_WINDOW:
                logger.debug(
                    f"Not enough review history to detect stuck loop "
                    f"({len(state.review_history)}/{self.STUCK_CHECK_WINDOW})"
                )
                return False, ""

            # Get last N reviews
            recent_reviews = state.review_history[-self.STUCK_CHECK_WINDOW :]

            # Extract error summaries from reviews
            error_summaries = []
            for review in recent_reviews:
                # Combine blocking and non-blocking issues into error summary
                blocking = review.get("blocking_issues", [])
                non_blocking = review.get("non_blocking_issues", [])
                all_issues = blocking + non_blocking

                if all_issues:
                    error_summary = " ".join(all_issues)
                    error_summaries.append(error_summary)

            # Need at least 2 error summaries to compare
            if len(error_summaries) < 2:
                logger.debug("Not enough errors in recent reviews to detect pattern")
                return False, ""

            # Check similarity between consecutive error summaries
            similar_pairs = []
            for i in range(len(error_summaries) - 1):
                similarity = self._calculate_similarity(
                    error_summaries[i], error_summaries[i + 1]
                )

                if similarity >= self.SIMILARITY_THRESHOLD:
                    similar_pairs.append((i, i + 1, similarity))
                    logger.debug(
                        f"High similarity ({similarity:.2%}) between "
                        f"reviews {i} and {i+1}"
                    )

            # If we have multiple similar pairs, agent is likely stuck
            if len(similar_pairs) >= 2:
                reason = (
                    f"Detected repeating error pattern in last {self.STUCK_CHECK_WINDOW} reviews. "
                    f"Similar errors appearing in {len(similar_pairs)} consecutive review pairs. "
                    f"The agent appears unable to resolve: {error_summaries[-1][:200]}..."
                )

                logger.warning(f"Stuck loop detected for issue #{state.issue_number}")
                return True, reason

            # Check if same errors appear in all recent reviews
            if len(error_summaries) == self.STUCK_CHECK_WINDOW:
                avg_similarity = sum(
                    self._calculate_similarity(error_summaries[0], err)
                    for err in error_summaries[1:]
                ) / (len(error_summaries) - 1)

                if avg_similarity >= self.SIMILARITY_THRESHOLD:
                    reason = (
                        f"Same errors repeating across all {self.STUCK_CHECK_WINDOW} recent reviews "
                        f"(average similarity: {avg_similarity:.2%}). "
                        f"Persistent issue: {error_summaries[-1][:200]}..."
                    )

                    logger.warning(
                        f"Stuck loop detected for issue #{state.issue_number} "
                        f"(persistent errors)"
                    )
                    return True, reason

            logger.debug(f"No stuck loop detected for issue #{state.issue_number}")
            return False, ""

        except Exception as e:
            logger.error(f"Error during stuck loop detection: {e}")
            # On error, fail safe by not marking as stuck
            return False, ""

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity ratio between two text strings.

        Uses difflib's SequenceMatcher for simple string similarity.

        Args:
            text1: First text string
            text2: Second text string

        Returns:
            Similarity ratio between 0.0 and 1.0
        """
        if not text1 or not text2:
            return 0.0

        # Normalize whitespace for better comparison
        text1_normalized = " ".join(text1.split()).lower()
        text2_normalized = " ".join(text2.split()).lower()

        matcher = SequenceMatcher(None, text1_normalized, text2_normalized)
        return matcher.ratio()

    def delete_state(self, issue_number: int) -> bool:
        """Delete state file for given issue.

        Args:
            issue_number: GitHub issue number

        Returns:
            True if file was deleted, False if it didn't exist
        """
        try:
            file_path = self._get_state_file_path(issue_number)

            if file_path.exists():
                file_path.unlink()
                logger.info(f"Deleted state file for issue #{issue_number}")
                return True
            else:
                logger.debug(f"No state file to delete for issue #{issue_number}")
                return False

        except Exception as e:
            logger.error(f"Failed to delete state for issue #{issue_number}: {e}")
            raise

    def list_all_states(self) -> list[int]:
        """List all issue numbers that have saved states.

        Returns:
            List of issue numbers with saved states
        """
        try:
            issue_numbers = []

            for file_path in self.state_dir.glob("issue-*.json"):
                # Extract issue number from filename
                try:
                    issue_num_str = file_path.stem.replace("issue-", "")
                    issue_number = int(issue_num_str)
                    issue_numbers.append(issue_number)
                except ValueError:
                    logger.warning(f"Invalid state filename: {file_path.name}")
                    continue

            issue_numbers.sort()
            logger.debug(f"Found {len(issue_numbers)} saved states")
            return issue_numbers

        except Exception as e:
            logger.error(f"Failed to list states: {e}")
            raise
