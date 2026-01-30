"""Redis-based state management for agent processing."""

import json
import logging
from typing import Optional, Tuple
from datetime import datetime
from difflib import SequenceMatcher

from redis import Redis

from src.common.models import AgentState

logger = logging.getLogger(__name__)


class StateManagerBase:
    """Base class defining state manager interface."""

    SIMILARITY_THRESHOLD = 0.7  # 70% similarity to consider errors as repeating
    STUCK_CHECK_WINDOW = 3  # Check last 3 reviews for stuck detection

    def get_state(self, issue_number: int) -> Optional[AgentState]:
        """Get agent state for an issue."""
        raise NotImplementedError

    def save_state(self, state: AgentState) -> None:
        """Save agent state."""
        raise NotImplementedError

    def delete_state(self, issue_number: int) -> bool:
        """Delete agent state."""
        raise NotImplementedError

    def update_state(self, issue_number: int, **updates) -> AgentState:
        """Update specific fields in agent state."""
        state = self.get_state(issue_number)

        if state is None:
            logger.info(f"Creating new state for issue #{issue_number}")
            state = AgentState(issue_number=issue_number)

        for key, value in updates.items():
            if not hasattr(state, key):
                raise ValueError(f"Invalid field for AgentState: {key}")
            setattr(state, key, value)

        state.updated_at = datetime.utcnow()
        self.save_state(state)
        return state

    def detect_stuck_loop(self, state: AgentState) -> Tuple[bool, str]:
        """Detect if agent is stuck in a loop with repeating errors."""
        if len(state.review_history) < self.STUCK_CHECK_WINDOW:
            return False, ""

        recent_reviews = state.review_history[-self.STUCK_CHECK_WINDOW :]

        # Extract error summaries
        error_summaries = []
        for review in recent_reviews:
            blocking = review.blocking_issues or []
            non_blocking = review.non_blocking_issues or []
            all_issues = blocking + non_blocking

            if all_issues:
                error_summary = " ".join(all_issues)
                error_summaries.append(error_summary)

        if len(error_summaries) < 2:
            return False, ""

        # Check similarity between consecutive errors
        similar_pairs = []
        for i in range(len(error_summaries) - 1):
            similarity = self._calculate_similarity(
                error_summaries[i], error_summaries[i + 1]
            )
            if similarity >= self.SIMILARITY_THRESHOLD:
                similar_pairs.append((i, i + 1, similarity))

        if len(similar_pairs) >= 2:
            reason = (
                f"Detected repeating error pattern in last {self.STUCK_CHECK_WINDOW} reviews. "
                f"Similar errors appearing in {len(similar_pairs)} consecutive review pairs."
            )
            logger.warning(f"Stuck loop detected for issue #{state.issue_number}")
            return True, reason

        return False, ""

    @staticmethod
    def _calculate_similarity(text1: str, text2: str) -> float:
        """Calculate similarity ratio between two text strings."""
        if not text1 or not text2:
            return 0.0
        text1_normalized = " ".join(text1.split()).lower()
        text2_normalized = " ".join(text2.split()).lower()
        matcher = SequenceMatcher(None, text1_normalized, text2_normalized)
        return matcher.ratio()


class RedisStateManager(StateManagerBase):
    """Manages agent state in Redis."""

    def __init__(self, redis_conn: Redis, repository: str):
        """Initialize state manager.

        Args:
            redis_conn: Redis connection
            repository: Repository full name (owner/repo)
        """
        self.redis = redis_conn
        self.repository = repository
        self.ttl = 7 * 86400  # 7 days TTL

    def _get_key(self, issue_number: int) -> str:
        """Generate Redis key for issue state.

        Args:
            issue_number: Issue number

        Returns:
            Redis key string
        """
        return f"state:{self.repository}:issue:{issue_number}"

    def get_state(self, issue_number: int) -> Optional[AgentState]:
        """Get agent state for an issue.

        Args:
            issue_number: Issue number

        Returns:
            AgentState or None if not found
        """
        key = self._get_key(issue_number)
        data = self.redis.get(key)

        if not data:
            logger.debug(f"No state found for issue #{issue_number}")
            return None

        try:
            state_dict = json.loads(data)
            state = AgentState(**state_dict)
            logger.debug(f"Loaded state for issue #{issue_number}")
            return state
        except Exception as e:
            logger.error(f"Failed to parse state for issue #{issue_number}: {e}")
            return None

    def save_state(self, state: AgentState) -> None:
        """Save agent state.

        Args:
            state: Agent state to save
        """
        key = self._get_key(state.issue_number)

        try:
            # Update timestamp
            state.updated_at = datetime.utcnow()

            # Serialize to JSON
            state_json = state.model_dump_json()

            # Save with TTL
            self.redis.set(key, state_json, ex=self.ttl)

            logger.debug(
                f"Saved state for issue #{state.issue_number} "
                f"(status={state.status}, iteration={state.iteration})"
            )
        except Exception as e:
            logger.error(f"Failed to save state for issue #{state.issue_number}: {e}")
            raise

    def load_state(self, issue_number: int) -> Optional[AgentState]:
        """Load agent state (alias for get_state for backward compatibility).

        Args:
            issue_number: Issue number

        Returns:
            AgentState or None if not found
        """
        return self.get_state(issue_number)

    def delete_state(self, issue_number: int) -> bool:
        """Delete agent state.

        Args:
            issue_number: Issue number

        Returns:
            True if deleted, False if not found
        """
        key = self._get_key(issue_number)
        result = self.redis.delete(key)

        if result:
            logger.info(f"Deleted state for issue #{issue_number}")
        else:
            logger.debug(f"No state to delete for issue #{issue_number}")

        return bool(result)

    def list_active_issues(self) -> list[int]:
        """List all active issues for this repository.

        Returns:
            List of issue numbers with active state
        """
        pattern = f"state:{self.repository}:issue:*"
        keys = self.redis.keys(pattern)

        issue_numbers = []
        for key in keys:
            try:
                # Extract issue number from key
                issue_num = int(key.decode().split(":")[-1])
                issue_numbers.append(issue_num)
            except (ValueError, AttributeError):
                continue

        logger.debug(f"Found {len(issue_numbers)} active issues")
        return sorted(issue_numbers)
