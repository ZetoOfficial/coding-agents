"""LLM client with unified interface for OpenAI and YandexGPT.

This module provides a unified interface for calling different LLM providers
with structured output support using Pydantic models.
"""

import json
import logging
import time
from collections import deque
from datetime import datetime, timedelta
from typing import TypeVar

import httpx
from openai import OpenAI
from pydantic import BaseModel, ValidationError

from src.common.config import AgentConfig

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Token counting (approximate)
CHARS_PER_TOKEN = 4


class RateLimiter:
    """Simple rate limiter for LLM API calls."""

    def __init__(self, max_requests_per_minute: int):
        """Initialize rate limiter.

        Args:
            max_requests_per_minute: Maximum number of requests allowed per minute
        """
        self.max_requests = max_requests_per_minute
        self.requests: deque[datetime] = deque()

    def wait_if_needed(self) -> None:
        """Wait if rate limit would be exceeded."""
        now = datetime.now()
        cutoff = now - timedelta(minutes=1)

        # Remove old requests
        while self.requests and self.requests[0] < cutoff:
            self.requests.popleft()

        # Check if we need to wait
        if len(self.requests) >= self.max_requests:
            sleep_time = (self.requests[0] - cutoff).total_seconds()
            if sleep_time > 0:
                logger.info(f"Rate limit reached, waiting {sleep_time:.2f} seconds")
                time.sleep(sleep_time)
                # Remove the oldest request after waiting
                self.requests.popleft()

        # Record this request
        self.requests.append(now)


class LLMError(Exception):
    """Base exception for LLM-related errors."""

    pass


class LLMValidationError(LLMError):
    """Raised when LLM output doesn't match expected schema."""

    pass


class LLMAPIError(LLMError):
    """Raised when LLM API call fails."""

    pass


def count_tokens(text: str) -> int:
    """Estimate token count from text.

    Args:
        text: Input text

    Returns:
        Estimated token count
    """
    return len(text) // CHARS_PER_TOKEN


class OpenAIClient:
    """OpenAI API client with structured output support."""

    def __init__(self, api_key: str, model: str, rate_limiter: RateLimiter):
        """Initialize OpenAI client.

        Args:
            api_key: OpenAI API key
            model: Model name to use
            rate_limiter: Rate limiter instance
        """
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.rate_limiter = rate_limiter
        logger.info(f"Initialized OpenAI client with model: {model}")

    def call_structured(self, prompt: str, response_model: type[T], max_retries: int = 3) -> T:
        """Call OpenAI with structured output.

        Args:
            prompt: Input prompt
            response_model: Pydantic model for response
            max_retries: Maximum number of retry attempts

        Returns:
            Parsed response as Pydantic model instance

        Raises:
            LLMAPIError: If API call fails after retries
            LLMValidationError: If response doesn't match schema
        """
        self.rate_limiter.wait_if_needed()

        last_error: Exception | None = None

        for attempt in range(max_retries):
            try:
                logger.debug(
                    f"OpenAI API call attempt {attempt + 1}/{max_retries}, "
                    f"tokens: ~{count_tokens(prompt)}"
                )

                # Use OpenAI's structured output feature (beta)
                completion = self.client.beta.chat.completions.parse(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert software engineer. "
                            "Respond with valid JSON matching the provided schema.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    response_format=response_model,
                    temperature=0.2,  # Lower temperature for more consistent output
                )

                # Extract the parsed response
                parsed = completion.choices[0].message.parsed

                if parsed is None:
                    raise LLMValidationError("OpenAI returned None for parsed response")

                logger.info(
                    f"OpenAI call successful, "
                    f"tokens used: {completion.usage.total_tokens if completion.usage else 'unknown'}"
                )

                return parsed

            except ValidationError as e:
                last_error = e
                logger.warning(f"Validation error on attempt {attempt + 1}: {e}")

            except Exception as e:
                last_error = e
                logger.warning(f"API error on attempt {attempt + 1}: {e}")

                # Exponential backoff
                if attempt < max_retries - 1:
                    sleep_time = 2**attempt
                    logger.info(f"Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)

        # All retries exhausted
        error_msg = f"OpenAI API call failed after {max_retries} attempts: {last_error}"
        logger.error(error_msg)
        raise LLMAPIError(error_msg) from last_error

    def call_text(self, prompt: str, max_retries: int = 3) -> str:
        """Call OpenAI for text completion.

        Args:
            prompt: Input prompt
            max_retries: Maximum number of retry attempts

        Returns:
            Generated text response

        Raises:
            LLMAPIError: If API call fails after retries
        """
        self.rate_limiter.wait_if_needed()

        last_error: Exception | None = None

        for attempt in range(max_retries):
            try:
                logger.debug(
                    f"OpenAI text call attempt {attempt + 1}/{max_retries}, "
                    f"tokens: ~{count_tokens(prompt)}"
                )

                completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert software engineer.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                )

                response = completion.choices[0].message.content

                if not response:
                    raise LLMAPIError("OpenAI returned empty response")

                logger.info(
                    f"OpenAI text call successful, "
                    f"tokens used: {completion.usage.total_tokens if completion.usage else 'unknown'}"
                )

                return response

            except Exception as e:
                last_error = e
                logger.warning(f"API error on attempt {attempt + 1}: {e}")

                # Exponential backoff
                if attempt < max_retries - 1:
                    sleep_time = 2**attempt
                    logger.info(f"Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)

        error_msg = f"OpenAI text call failed after {max_retries} attempts: {last_error}"
        logger.error(error_msg)
        raise LLMAPIError(error_msg) from last_error


class YandexGPTClient:
    """YandexGPT API client with structured output support."""

    def __init__(
        self,
        api_key: str,
        folder_id: str,
        model: str,
        rate_limiter: RateLimiter,
    ):
        """Initialize YandexGPT client.

        Args:
            api_key: Yandex API key
            folder_id: Yandex Cloud folder ID
            model: Model URI or name
            rate_limiter: Rate limiter instance
        """
        self.api_key = api_key
        self.folder_id = folder_id
        self.model = model
        self.rate_limiter = rate_limiter
        self.base_url = "https://llm.api.cloud.yandex.net/foundationModels/v1"
        logger.info(f"Initialized YandexGPT client with model: {model}")

    def _get_model_uri(self) -> str:
        """Get full model URI for YandexGPT.

        Returns:
            Full model URI
        """
        if self.model.startswith("gpt://"):
            return self.model
        return f"gpt://{self.folder_id}/{self.model}"

    def _call_api(self, prompt: str, max_retries: int = 3) -> str:
        """Make API call to YandexGPT.

        Args:
            prompt: Input prompt
            max_retries: Maximum number of retry attempts

        Returns:
            Raw response text

        Raises:
            LLMAPIError: If API call fails
        """
        self.rate_limiter.wait_if_needed()

        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "modelUri": self._get_model_uri(),
            "completionOptions": {
                "stream": False,
                "temperature": 0.2,
                "maxTokens": 8000,
            },
            "messages": [
                {
                    "role": "system",
                    "text": "You are an expert software engineer. "
                    "Respond with valid JSON matching the provided schema.",
                },
                {"role": "user", "text": prompt},
            ],
        }

        last_error: Exception | None = None

        for attempt in range(max_retries):
            try:
                logger.debug(
                    f"YandexGPT API call attempt {attempt + 1}/{max_retries}, "
                    f"tokens: ~{count_tokens(prompt)}"
                )

                with httpx.Client(timeout=60.0) as client:
                    response = client.post(
                        f"{self.base_url}/completion",
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()

                data = response.json()
                result = data.get("result", {})
                alternatives = result.get("alternatives", [])

                if not alternatives:
                    raise LLMAPIError("YandexGPT returned no alternatives")

                text = alternatives[0].get("message", {}).get("text", "")

                if not text:
                    raise LLMAPIError("YandexGPT returned empty text")

                usage = result.get("usage", {})
                logger.info(
                    f"YandexGPT call successful, "
                    f"tokens used: {usage.get('totalTokens', 'unknown')}"
                )

                return text

            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(
                    f"HTTP error on attempt {attempt + 1}: {e.response.status_code} - {e.response.text}"
                )

            except Exception as e:
                last_error = e
                logger.warning(f"API error on attempt {attempt + 1}: {e}")

            # Exponential backoff
            if attempt < max_retries - 1:
                sleep_time = 2**attempt
                logger.info(f"Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)

        error_msg = f"YandexGPT API call failed after {max_retries} attempts: {last_error}"
        logger.error(error_msg)
        raise LLMAPIError(error_msg) from last_error

    def call_structured(self, prompt: str, response_model: type[T], max_retries: int = 3) -> T:
        """Call YandexGPT with structured output.

        Args:
            prompt: Input prompt
            response_model: Pydantic model for response
            max_retries: Maximum number of retry attempts

        Returns:
            Parsed response as Pydantic model instance

        Raises:
            LLMAPIError: If API call fails
            LLMValidationError: If response doesn't match schema
        """
        # Add schema information to prompt
        schema_json = response_model.model_json_schema()
        enhanced_prompt = (
            f"{prompt}\n\n"
            f"Output valid JSON matching this exact schema:\n"
            f"```json\n{json.dumps(schema_json, indent=2)}\n```\n\n"
            f"Respond ONLY with valid JSON, no other text."
        )

        response_text = self._call_api(enhanced_prompt, max_retries)

        # Parse JSON from response
        try:
            # Try to extract JSON from response (in case there's extra text)
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1

            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON object found in response")

            json_text = response_text[json_start:json_end]
            parsed_dict = json.loads(json_text)

            # Validate against Pydantic model
            result = response_model.model_validate(parsed_dict)
            logger.debug("Successfully validated YandexGPT response")

            return result

        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"Failed to parse/validate YandexGPT response: {e}")
            logger.debug(f"Raw response: {response_text[:500]}")
            raise LLMValidationError(f"Failed to parse structured output: {e}") from e

    def call_text(self, prompt: str, max_retries: int = 3) -> str:
        """Call YandexGPT for text completion.

        Args:
            prompt: Input prompt
            max_retries: Maximum number of retry attempts

        Returns:
            Generated text response

        Raises:
            LLMAPIError: If API call fails
        """
        return self._call_api(prompt, max_retries)


def create_llm_client(
    config: AgentConfig,
) -> OpenAIClient | YandexGPTClient:
    """Create appropriate LLM client based on configuration.

    Args:
        config: Agent configuration

    Returns:
        Configured LLM client

    Raises:
        ValueError: If provider configuration is invalid
    """
    rate_limiter = RateLimiter(config.max_llm_requests_per_minute)

    if config.llm_provider == "openai":
        api_key = config.get_openai_api_key()
        if not api_key:
            raise ValueError("OpenAI API key not configured")

        return OpenAIClient(
            api_key=api_key,
            model=config.openai_model,
            rate_limiter=rate_limiter,
        )

    elif config.llm_provider == "yandex":
        api_key = config.get_yandex_api_key()
        if not api_key:
            raise ValueError("Yandex API key not configured")

        if not config.yandex_folder_id:
            raise ValueError("Yandex folder ID not configured")

        return YandexGPTClient(
            api_key=api_key,
            folder_id=config.yandex_folder_id,
            model=config.yandex_model,
            rate_limiter=rate_limiter,
        )

    else:
        raise ValueError(f"Unsupported LLM provider: {config.llm_provider}")


def call_llm_structured(
    prompt: str,
    response_model: type[T],
    config: AgentConfig,
    max_retries: int = 3,
) -> T:
    """Call LLM with structured output using appropriate provider.

    This is the main entry point for making LLM calls with structured output.
    It handles provider selection, rate limiting, retries, and error handling.

    Args:
        prompt: Input prompt text
        response_model: Pydantic model class for response validation
        config: Agent configuration with API keys and settings
        max_retries: Maximum number of retry attempts on failure

    Returns:
        Validated Pydantic model instance

    Raises:
        LLMAPIError: If API call fails after all retries
        LLMValidationError: If response doesn't match expected schema
        ValueError: If configuration is invalid

    Example:
        >>> from src.common.models import RequirementAnalysis
        >>> from src.common.config import load_config
        >>> config = load_config()
        >>> analysis = call_llm_structured(
        ...     prompt="Analyze this issue: ...",
        ...     response_model=RequirementAnalysis,
        ...     config=config
        ... )
    """
    logger.info(
        f"Making structured LLM call with {response_model.__name__} " f"using {config.llm_provider}"
    )

    client = create_llm_client(config)

    try:
        result = client.call_structured(prompt, response_model, max_retries)
        logger.info(f"Successfully parsed {response_model.__name__}")
        return result

    except (LLMAPIError, LLMValidationError) as e:
        logger.error(f"LLM structured call failed: {e}")
        raise


def call_llm_text(
    prompt: str,
    config: AgentConfig,
    max_retries: int = 3,
) -> str:
    """Call LLM for text completion using appropriate provider.

    This is the main entry point for making LLM calls with unstructured text output.
    It handles provider selection, rate limiting, retries, and error handling.

    Args:
        prompt: Input prompt text
        config: Agent configuration with API keys and settings
        max_retries: Maximum number of retry attempts on failure

    Returns:
        Generated text response

    Raises:
        LLMAPIError: If API call fails after all retries
        ValueError: If configuration is invalid

    Example:
        >>> from src.common.config import load_config
        >>> config = load_config()
        >>> response = call_llm_text(
        ...     prompt="Explain this code: ...",
        ...     config=config
        ... )
    """
    logger.info(f"Making text LLM call using {config.llm_provider}")

    client = create_llm_client(config)

    try:
        result = client.call_text(prompt, max_retries)
        logger.info(f"Successfully generated text response ({len(result)} chars)")
        return result

    except LLMAPIError as e:
        logger.error(f"LLM text call failed: {e}")
        raise
