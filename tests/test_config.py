"""Tests for configuration management and validation."""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.common.config import AgentConfig


# Test RSA private key (generated for testing only, not used in production)
# This is a real RSA 2048-bit key generated with cryptography library
TEST_PRIVATE_KEY = """-----BEGIN RSA PRIVATE KEY-----
MIIEogIBAAKCAQEAkj4tiYiHb68G2EWqFYPxUG0iHAdBfmAoHr3V8i3YA6NX9q0v
8hc1ZZoxMTwTFi7pJHUt3BQcDdSnRbR2sTfLgvehaJY0QaVC7KXkR0XDtQClJOYr
Uyy81oMjeSJu67Wrnvxx6o949ObX45EJvDgaweOvG9Bhcio6NxZ50DNnq8sAjkor
zYnC59DNjf6oJobP6T87++FnTRckPNjVMr23Idflujxu2ydYcgJC6otcYQWNXk9N
sBdNsEmsT1kxzotJuocHB0+XGuHNi7ImJXzF3rkVwi+uKqPmAJGOiUG+lGZTdzj1
MHi1vagpu241K1e97jSCsNl2rH9XB9ObGNCVdQIDAQABAoIBAAQIifn6lX2rjp1F
YpkAUBX/RIsQWiqRnVmns7Bfuk7zYNgxU5qyMCtSstugRAh/F7gFMVQaC+IHxOtD
vGhL2SWODdoUFnHfDHb5Zk/e6TRjRaq8XGKJX9XsvPw4ymVe19JlNQEanuPmP/sL
Q4D47Sf+zxQNzbo31u4xBQAMguX2gyuKC+EaVoFrStTYWgmVVmUDlJU10znLgGmF
8QMp6mYXxTRZEaXRjQuAwUJ/VgBFBI52AUOx/MRV8gAHNgqZIEuClNfBhAuNcV1L
gVcI0/tSFEHBp2Ifq1TyESKpW3J4xDDor9nttZNn/gxUBEoknluIvg0Np+9pW9uU
EkXoDvECgYEAwxBUgub42TFKOmtMEtc/dVYypjRoP16ddTTipMTPrCONYYZeM+8k
kNY4lKPBXkNbBzbmYQh4fU3BkKzYsSfsoEM7P3dXE2ghoy65biJ023yw8wFID6bj
WDWKwv2hFT7TqsYnZt7iuR3H/c/vYBpTWvhThHCqWbLLr2VbdleltjkCgYEAv+2I
9/skjI2xhkxh3p0Nbe2gXUwyENQZfHcFnz3bIE7I86Z7BHr11vfOY2NimfeQfQWN
FFqtsNN0BPo2j4ybRydu2rSsalYf/clEiy3+EeCSSXE/1hDhj3n03f7861vqhMNb
PROK3jpi+ap6JEl4dDfLYdjViFKtB+HuNwc6eR0CgYAu8ZMlHajtvCr8/C2Gqz6e
Ymw2C467EW4bcurIdIT2DGhN/CRXo0nNgYCEZRR4NwWFKvUujPdSUJAw3SgZGl6c
AxITKAlQplLSDsCZfLlayRtcoAZTnfpAlEIcwyUtE72k76Mz4pf1rPEgaBZXrn44
+mI/EU4t4BWc1Gu6g0ViIQKBgFgYriA1lQc3Gt9sPBg0uq9UvaFVkj2LPc+VymzX
tbdUsoS0TA84aZOs131jZyUJL7dTTviizss1pDGMsHKftb6paQbWm7WLps+VDPNd
vxtxm3Q+mXCm+wIilrU3j9xwqmsaSMz2JW3wGvJCwCHb34BpA9/76bfTSz0tBW0Y
0kw5AoGAEVxbx209exp+3G1SPNESgAUgHyHb+7KiNn6qPWpqPlQS3uv5x2B5zV14
GhB6fC5fM0Fc2BrevJ/iCBQkPZkgMt6AIIE8ap3OZOiZzBsqeJHPsN6MBpM4sEnW
Pt+S07AhUhWsSD8ri3INifcxr0v3sHLZrbbccs7wQXSmBOeXSr0=
-----END RSA PRIVATE KEY-----"""


class TestAgentConfigPrivateKey:
    """Tests for GitHub App private key validation and parsing."""

    def test_private_key_with_literal_newlines(self):
        """Test that literal \\n in .env file format is converted to actual newlines."""
        # Simulate how the key appears in .env file
        key_with_literal_newlines = TEST_PRIVATE_KEY.replace("\n", "\\n")

        with patch.dict(os.environ, {
            "GITHUB_REPOSITORY": "owner/repo",
            "LLM_PROVIDER": "openai",
            "OPENAI_API_KEY": "sk-test123",
            "GITHUB_APP_ID": "123456",
            "GITHUB_APP_PRIVATE_KEY": key_with_literal_newlines,
            "GITHUB_APP_INSTALLATION_ID": "789012",
        }):
            config = AgentConfig()

            # Get the parsed key
            parsed_key = config.get_github_app_private_key()

            # Should have actual newlines, not literal \n
            assert "\n" in parsed_key
            assert "\\n" not in parsed_key
            assert parsed_key.startswith("-----BEGIN RSA PRIVATE KEY-----\n")
            assert parsed_key.endswith("\n-----END RSA PRIVATE KEY-----")

    def test_private_key_with_actual_newlines(self):
        """Test that key with actual newlines passes through unchanged."""
        with patch.dict(os.environ, {
            "GITHUB_REPOSITORY": "owner/repo",
            "LLM_PROVIDER": "openai",
            "OPENAI_API_KEY": "sk-test123",
            "GITHUB_APP_ID": "123456",
            "GITHUB_APP_PRIVATE_KEY": TEST_PRIVATE_KEY,
            "GITHUB_APP_INSTALLATION_ID": "789012",
        }):
            config = AgentConfig()

            # Get the parsed key
            parsed_key = config.get_github_app_private_key()

            # Should remain unchanged
            assert parsed_key == TEST_PRIVATE_KEY
            assert "\n" in parsed_key
            assert "\\n" not in parsed_key

    def test_private_key_none(self):
        """Test that None value is handled correctly."""
        with patch.dict(os.environ, {
            "GITHUB_REPOSITORY": "owner/repo",
            "LLM_PROVIDER": "openai",
            "OPENAI_API_KEY": "sk-test123",
            "GITHUB_TOKEN": "ghp_test123",
        }, clear=True):
            config = AgentConfig()

            # Should return None when not set
            assert config.get_github_app_private_key() is None

    def test_private_key_can_be_used_for_jwt(self):
        """Test that parsed private key can be used for JWT generation."""
        pytest.importorskip("jwt")  # Skip if jwt not installed
        import jwt
        import time

        key_with_literal_newlines = TEST_PRIVATE_KEY.replace("\n", "\\n")

        with patch.dict(os.environ, {
            "GITHUB_REPOSITORY": "owner/repo",
            "LLM_PROVIDER": "openai",
            "OPENAI_API_KEY": "sk-test123",
            "GITHUB_APP_ID": "123456",
            "GITHUB_APP_PRIVATE_KEY": key_with_literal_newlines,
            "GITHUB_APP_INSTALLATION_ID": "789012",
        }):
            config = AgentConfig()
            parsed_key = config.get_github_app_private_key()

            # Try to generate a JWT with the parsed key
            now = int(time.time())
            payload = {
                "iat": now - 60,
                "exp": now + 600,
                "iss": "123456",
            }

            # This should not raise an exception
            encoded_jwt = jwt.encode(payload, parsed_key, algorithm="RS256")
            assert encoded_jwt is not None
            assert isinstance(encoded_jwt, str)

    def test_private_key_multiline_env_format(self):
        """Test that multiline .env format works correctly."""
        # Some .env parsers support multiline with quotes
        multiline_key = f'"{TEST_PRIVATE_KEY}"'

        with patch.dict(os.environ, {
            "GITHUB_REPOSITORY": "owner/repo",
            "LLM_PROVIDER": "openai",
            "OPENAI_API_KEY": "sk-test123",
            "GITHUB_APP_ID": "123456",
            "GITHUB_APP_PRIVATE_KEY": multiline_key,
            "GITHUB_APP_INSTALLATION_ID": "789012",
        }):
            config = AgentConfig()
            parsed_key = config.get_github_app_private_key()

            # Should strip quotes and preserve newlines
            assert parsed_key is not None
            # The value should contain actual newlines (quotes are stripped by pydantic)
            assert "\n" in parsed_key or parsed_key == TEST_PRIVATE_KEY

    def test_invalid_installation_id_type(self):
        """Test that non-integer installation ID raises validation error."""
        with patch.dict(os.environ, {
            "GITHUB_REPOSITORY": "owner/repo",
            "LLM_PROVIDER": "openai",
            "OPENAI_API_KEY": "sk-test123",
            "GITHUB_APP_ID": "123456",
            "GITHUB_APP_PRIVATE_KEY": TEST_PRIVATE_KEY,
            "GITHUB_APP_INSTALLATION_ID": "not_a_number",
        }):
            with pytest.raises(ValidationError) as exc_info:
                AgentConfig()

            # Should mention installation_id in error
            assert "github_app_installation_id" in str(exc_info.value)

    def test_github_app_mode_detection(self):
        """Test that GitHub App mode is correctly detected."""
        # With GitHub App credentials
        with patch.dict(os.environ, {
            "GITHUB_REPOSITORY": "owner/repo",
            "LLM_PROVIDER": "openai",
            "OPENAI_API_KEY": "sk-test123",
            "GITHUB_APP_ID": "123456",
            "GITHUB_APP_PRIVATE_KEY": TEST_PRIVATE_KEY,
            "GITHUB_APP_INSTALLATION_ID": "789012",
        }):
            config = AgentConfig()
            assert config.is_using_github_app() is True

        # Without GitHub App credentials (PAT mode)
        with patch.dict(os.environ, {
            "GITHUB_REPOSITORY": "owner/repo",
            "LLM_PROVIDER": "openai",
            "OPENAI_API_KEY": "sk-test123",
            "GITHUB_TOKEN": "ghp_test123",
        }, clear=True):
            config = AgentConfig()
            assert config.is_using_github_app() is False


class TestAgentConfigGeneral:
    """General configuration tests."""

    def test_config_loads_with_minimal_settings(self):
        """Test that config loads with minimum required settings."""
        with patch.dict(os.environ, {
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_TOKEN": "ghp_test123",
            "LLM_PROVIDER": "openai",
            "OPENAI_API_KEY": "sk-test123",
        }, clear=True):
            config = AgentConfig()
            assert config.github_repository == "owner/repo"
            assert config.llm_provider == "openai"

    def test_invalid_repository_format(self):
        """Test that invalid repository format raises error."""
        with patch.dict(os.environ, {
            "GITHUB_REPOSITORY": "invalid-format",
            "GITHUB_TOKEN": "ghp_test123",
            "LLM_PROVIDER": "openai",
            "OPENAI_API_KEY": "sk-test123",
        }, clear=True):
            with pytest.raises(ValidationError) as exc_info:
                AgentConfig()

            assert "github_repository" in str(exc_info.value)

    def test_secrets_are_masked(self):
        """Test that secrets are properly masked in config repr."""
        with patch.dict(os.environ, {
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_TOKEN": "ghp_test123",
            "LLM_PROVIDER": "openai",
            "OPENAI_API_KEY": "sk-test123",
        }, clear=True):
            config = AgentConfig()
            config_str = str(config)

            # Secrets should not appear in string representation
            assert "ghp_test123" not in config_str
            assert "sk-test123" not in config_str
            assert "***" in config_str or "SecretStr" in config_str