"""Configuration management with pydantic and environment variable loading."""

import os
import re
import logging
from typing import Optional, Literal
from pydantic import SecretStr, field_validator, model_validator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SecretFilter(logging.Filter):
    """Filter to redact secrets from log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        # Redact common secret patterns
        patterns = [
            (r"ghp_[a-zA-Z0-9]{36,}", "[GITHUB_TOKEN_REDACTED]"),
            (r"sk-[a-zA-Z0-9]{48,}", "[OPENAI_KEY_REDACTED]"),
            (r"Bearer\s+[a-zA-Z0-9\-._~+/]+=*", "Bearer [TOKEN_REDACTED]"),
        ]
        for pattern, replacement in patterns:
            message = re.sub(pattern, replacement, message)
        record.msg = message
        return True


class AgentConfig(BaseSettings):
    """Main configuration for the SDLC agent system."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # GitHub Configuration
    github_token: Optional[SecretStr] = Field(
        default=None, description="GitHub personal access token (for Actions)"
    )
    github_repository: str = Field(description="Repository in format owner/repo")

    # GitHub App Configuration (for webhook server)
    github_app_id: Optional[str] = Field(
        default=None, description="GitHub App ID"
    )
    github_app_private_key: Optional[SecretStr] = Field(
        default=None, description="GitHub App private key (PEM format)"
    )
    github_app_installation_id: Optional[int] = Field(
        default=None, description="GitHub App installation ID"
    )
    webhook_secret: Optional[SecretStr] = Field(
        default=None, description="GitHub webhook secret for signature verification"
    )

    # LLM Provider Configuration
    llm_provider: Literal["openai", "yandex"] = Field(
        default="openai", description="LLM provider to use"
    )

    # OpenAI Configuration
    openai_api_key: Optional[SecretStr] = Field(
        default=None, description="OpenAI API key"
    )
    openai_model: str = Field(default="gpt-4o-mini", description="OpenAI model to use")

    # YandexGPT Configuration
    yandex_api_key: Optional[SecretStr] = Field(
        default=None, description="Yandex API key"
    )
    yandex_model: str = Field(
        default="yandexgpt-latest", description="Yandex model to use"
    )
    yandex_folder_id: Optional[str] = Field(
        default=None, description="Yandex Cloud folder ID"
    )

    # Agent Configuration
    max_iterations: int = Field(default=5, description="Maximum iteration limit", ge=1, le=10)
    agent_timeout_minutes: int = Field(
        default=30, description="Timeout for agent operations", ge=5, le=120
    )
    default_branch: str = Field(default="main", description="Default base branch")
    work_branch_prefix: str = Field(
        default="agent/issue-", description="Prefix for work branches"
    )

    # Logging Configuration
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: Literal["json", "text"] = Field(
        default="text", description="Log output format"
    )

    # Security Configuration
    min_coverage_percent: float = Field(
        default=70.0, description="Minimum code coverage percentage", ge=0.0, le=100.0
    )
    enable_security_checks: bool = Field(
        default=True, description="Enable security analysis"
    )

    # Rate Limiting
    max_llm_requests_per_minute: int = Field(
        default=10, description="Max LLM requests per minute", ge=1
    )
    max_github_requests_per_hour: int = Field(
        default=5000, description="Max GitHub API requests per hour", ge=100
    )

    # Redis Configuration (for task queue and state)
    redis_url: Optional[str] = Field(
        default=None, description="Redis connection URL"
    )

    @field_validator("llm_provider", mode="after")
    @classmethod
    def validate_llm_provider(cls, v: str) -> str:
        """Validate LLM provider value."""
        if v not in ["openai", "yandex"]:
            raise ValueError("llm_provider must be 'openai' or 'yandex'")
        return v

    @model_validator(mode="after")
    def validate_api_keys(self) -> "AgentConfig":
        """Validate that required API keys are present for the selected provider."""
        if self.llm_provider == "openai" and not self.openai_api_key:
            raise ValueError("openai_api_key is required when llm_provider is 'openai'")
        if self.llm_provider == "yandex" and not self.yandex_api_key:
            raise ValueError("yandex_api_key is required when llm_provider is 'yandex'")

        # Validate GitHub authentication (either PAT or App credentials)
        has_pat = self.github_token is not None
        has_app_auth = all([
            self.github_app_id,
            self.github_app_private_key,
            self.github_app_installation_id
        ])
        if not (has_pat or has_app_auth):
            raise ValueError(
                "Either github_token (PAT) or GitHub App credentials "
                "(app_id + private_key + installation_id) must be provided"
            )

        return self

    @field_validator("github_repository")
    @classmethod
    def validate_github_repository(cls, v: str) -> str:
        """Validate GitHub repository format."""
        if not re.match(r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$", v):
            raise ValueError(
                "github_repository must be in format 'owner/repo'"
            )
        return v

    def __repr__(self) -> str:
        """Prevent secrets from being printed."""
        return (
            f"AgentConfig(github_token={'***' if self.github_token else None}, "
            f"github_app_id={self.github_app_id or None}, "
            f"openai_api_key={'***' if self.openai_api_key else None}, "
            f"yandex_api_key={'***' if self.yandex_api_key else None}, "
            f"llm_provider={self.llm_provider})"
        )

    def get_github_token(self) -> Optional[str]:
        """Get GitHub token as plain string."""
        if self.github_token:
            return self.github_token.get_secret_value()
        return None

    def get_github_app_private_key(self) -> Optional[str]:
        """Get GitHub App private key as plain string."""
        if self.github_app_private_key:
            return self.github_app_private_key.get_secret_value()
        return None

    def get_webhook_secret(self) -> Optional[str]:
        """Get webhook secret as plain string."""
        if self.webhook_secret:
            return self.webhook_secret.get_secret_value()
        return None

    def get_openai_api_key(self) -> Optional[str]:
        """Get OpenAI API key as plain string."""
        if self.openai_api_key:
            return self.openai_api_key.get_secret_value()
        return None

    def get_yandex_api_key(self) -> Optional[str]:
        """Get Yandex API key as plain string."""
        if self.yandex_api_key:
            return self.yandex_api_key.get_secret_value()
        return None

    def is_using_github_app(self) -> bool:
        """Check if using GitHub App authentication instead of PAT."""
        return all([
            self.github_app_id,
            self.github_app_private_key,
            self.github_app_installation_id
        ])


def setup_logging(config: AgentConfig) -> None:
    """Configure logging with secret filtering."""
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)

    handlers = [logging.StreamHandler()]

    if config.log_format == "json":
        # For production/GitHub Actions, use structured logging
        log_format = '{"time":"%(asctime)s","level":"%(levelname)s","module":"%(name)s","message":"%(message)s"}'
    else:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=handlers,
        force=True,
    )

    # Add secret filter to all handlers
    secret_filter = SecretFilter()
    for handler in logging.root.handlers:
        handler.addFilter(secret_filter)

    # Disable httpx logging to avoid formatting errors
    logging.getLogger("httpx").setLevel(logging.WARNING)


def load_config() -> AgentConfig:
    """Load and validate configuration from environment."""
    config = AgentConfig()
    setup_logging(config)
    return config
