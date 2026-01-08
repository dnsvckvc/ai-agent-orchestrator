"""
LLM integration package for multi-provider support.

Provides a unified interface for interacting with different LLM providers
including OpenAI and Anthropic Claude.

Example usage:
    >>> from llm import LLMClient
    >>>
    >>> # Simple usage with environment variables
    >>> client = LLMClient.from_env("openai", model="gpt-4")
    >>> response = await client.complete("Summarize this text...")
    >>>
    >>> # Advanced usage with custom config
    >>> from llm import LLMConfig, LLMProvider
    >>> config = LLMConfig(
    ...     provider=LLMProvider.ANTHROPIC,
    ...     model="claude-3-5-sonnet-20241022",
    ...     temperature=0.5,
    ...     max_tokens=2000
    ... )
    >>> client = LLMClient(config)
    >>> response = await client.complete_with_system(
    ...     system_prompt="You are a helpful assistant",
    ...     user_prompt="Hello!"
    ... )
"""

from .base_provider import (
    BaseLLMProvider,
    LLMConfig,
    LLMMessage,
    LLMProvider,
    LLMResponse,
)
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider
from .provider_factory import LLMProviderFactory, LLMClient

__all__ = [
    "BaseLLMProvider",
    "LLMConfig",
    "LLMMessage",
    "LLMProvider",
    "LLMResponse",
    "OpenAIProvider",
    "AnthropicProvider",
    "LLMProviderFactory",
    "LLMClient",
]
