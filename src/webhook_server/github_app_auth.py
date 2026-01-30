"""GitHub App authentication - JWT generation and installation token management."""

import time
import logging
from datetime import datetime, timedelta
from typing import Optional

import jwt
from github import Github, GithubIntegration

from src.common.config import AgentConfig

logger = logging.getLogger(__name__)


class GitHubAppAuth:
    """Handles GitHub App authentication flow."""

    def __init__(self, config: AgentConfig):
        """Initialize GitHub App authentication.

        Args:
            config: Agent configuration with GitHub App credentials
        """
        if not config.is_using_github_app():
            raise ValueError("GitHub App credentials not configured")

        self.app_id = config.github_app_id
        self.private_key = config.get_github_app_private_key()
        self.installation_id = config.github_app_installation_id

        if not all([self.app_id, self.private_key, self.installation_id]):
            raise ValueError("Missing GitHub App credentials")

        # Debug logging for private key
        if self.private_key:
            key_preview = self.private_key[:80].replace("\n", "\\n")
            logger.debug(
                f"GitHubAppAuth initialized: app_id={self.app_id}, "
                f"installation_id={self.installation_id}, "
                f"key_length={len(self.private_key)}, "
                f"key_has_newlines={chr(10) in self.private_key}, "
                f"key_starts_with={repr(key_preview)}"
            )

        self._token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    def generate_jwt(self) -> str:
        """Generate GitHub App JWT token (valid 10 minutes).

        Returns:
            JWT token string
        """
        now = int(time.time())
        payload = {
            "iat": now - 60,  # Issued at time (60 seconds in the past to allow for clock drift)
            "exp": now + (10 * 60),  # JWT expiration time (10 minutes from now)
            "iss": self.app_id,  # GitHub App's identifier
        }

        encoded_jwt = jwt.encode(payload, self.private_key, algorithm="RS256")
        logger.debug(f"Generated JWT for GitHub App ID {self.app_id}")
        return encoded_jwt

    def get_installation_token(self, force_refresh: bool = False) -> str:
        """Get installation access token (valid 1 hour, cached).

        Args:
            force_refresh: Force token refresh even if cached token is valid

        Returns:
            Installation access token
        """
        # Check if we have a valid cached token
        if not force_refresh and self._token and self._token_expires_at:
            # Refresh 5 minutes before expiration to avoid race conditions
            if datetime.utcnow() < self._token_expires_at - timedelta(minutes=5):
                logger.debug("Using cached installation token")
                return self._token

        # Generate new JWT and get installation token
        jwt_token = self.generate_jwt()

        # Use PyGithub's GithubIntegration to get installation token
        integration = GithubIntegration(self.app_id, self.private_key)
        auth = integration.get_access_token(self.installation_id)

        self._token = auth.token
        self._token_expires_at = auth.expires_at

        logger.info(
            f"Refreshed installation token for installation {self.installation_id}, "
            f"expires at {self._token_expires_at}"
        )

        return self._token

    def get_github_client(self) -> Github:
        """Get authenticated PyGithub client.

        Returns:
            Authenticated Github client
        """
        token = self.get_installation_token()
        return Github(token)


def get_installation_token_for_config(config: AgentConfig) -> str:
    """Helper function to get installation token from config.

    Args:
        config: Agent configuration

    Returns:
        Installation access token

    Raises:
        ValueError: If GitHub App is not configured
    """
    auth = GitHubAppAuth(config)
    return auth.get_installation_token()
