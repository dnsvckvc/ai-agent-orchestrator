"""
LLM Provider Factory for creating provider instances.
"""
from typing import Dict, Type
from .base_provider import BaseLLMProvider, LLMConfig, LLMProvider
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider


class LLMProviderFactory:
    """
    Factory for creating LLM provider instances.
    Supports registration of custom providers.
    """

    _providers: Dict[LLMProvider, Type[BaseLLMProvider]] = {
        LLMProvider.OPENAI: OpenAIProvider,
        LLMProvider.ANTHROPIC: AnthropicProvider,
    }

    @classmethod
    def create_provider(cls, config: LLMConfig) -> BaseLLMProvider:
        """
        Create an LLM provider instance based on configuration.

        Args:
            config: LLM configuration with provider type

        Returns:
            Initialized provider instance

        Raises:
            ValueError: If provider type is not supported
        """
        provider_class = cls._providers.get(config.provider)

        if provider_class is None:
            raise ValueError(
                f"Unsupported provider: {config.provider}. "
                f"Supported providers: {list(cls._providers.keys())}"
            )

        return provider_class(config)

    @classmethod
    def register_provider(
        cls,
        provider_type: LLMProvider,
        provider_class: Type[BaseLLMProvider]
    ):
        """
        Register a custom provider implementation.

        Args:
            provider_type: Provider enum type
            provider_class: Provider implementation class

        Example:
            >>> class MyCustomProvider(BaseLLMProvider):
            ...     pass
            >>> LLMProviderFactory.register_provider(
            ...     LLMProvider.CUSTOM,
            ...     MyCustomProvider
            ... )
        """
        cls._providers[provider_type] = provider_class

    @classmethod
    def get_supported_providers(cls) -> list[str]:
        """Get list of supported provider names."""
        return [provider.value for provider in cls._providers.keys()]


class LLMClient:
    """
    High-level LLM client that simplifies provider usage.
    Provides a unified interface for all providers.
    """

    def __init__(self, config: LLMConfig):
        """
        Initialize LLM client with configuration.

        Args:
            config: LLM configuration
        """
        self.config = config
        self.provider = LLMProviderFactory.create_provider(config)

    async def complete(self, prompt: str, **kwargs):
        """
        Simple completion with a single prompt.

        Args:
            prompt: Text prompt
            **kwargs: Additional parameters for provider

        Returns:
            LLMResponse
        """
        from .base_provider import LLMMessage

        messages = [LLMMessage(role="user", content=prompt)]
        return await self.provider.complete(messages, **kwargs)

    async def complete_with_system(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs
    ):
        """
        Completion with system and user prompts.

        Args:
            system_prompt: System instruction
            user_prompt: User query
            **kwargs: Additional parameters

        Returns:
            LLMResponse
        """
        from .base_provider import LLMMessage

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt),
        ]
        return await self.provider.complete(messages, **kwargs)

    async def chat(self, messages: list, **kwargs):
        """
        Multi-turn conversation.

        Args:
            messages: List of message dicts with 'role' and 'content'
            **kwargs: Additional parameters

        Returns:
            LLMResponse
        """
        from .base_provider import LLMMessage

        formatted_messages = [
            LLMMessage(role=msg["role"], content=msg["content"])
            for msg in messages
        ]
        return await self.provider.complete(formatted_messages, **kwargs)

    async def stream(self, prompt: str, **kwargs):
        """
        Stream completion tokens.

        Args:
            prompt: Text prompt
            **kwargs: Additional parameters

        Yields:
            Response chunks
        """
        from .base_provider import LLMMessage

        messages = [LLMMessage(role="user", content=prompt)]
        async for chunk in self.provider.stream_complete(messages, **kwargs):
            yield chunk

    @staticmethod
    def from_env(
        provider: str = "openai",
        model: str = None,
        **kwargs
    ) -> "LLMClient":
        """
        Create client from environment variables.

        Args:
            provider: Provider name ("openai" or "anthropic")
            model: Model name (uses defaults if not specified)
            **kwargs: Additional config parameters

        Returns:
            Configured LLMClient instance

        Example:
            >>> client = LLMClient.from_env("openai", model="gpt-4")
            >>> response = await client.complete("Hello!")
        """
        provider_enum = LLMProvider(provider)

        # Default models
        default_models = {
            LLMProvider.OPENAI: "gpt-4-turbo",
            LLMProvider.ANTHROPIC: "claude-3-5-sonnet-20241022",
        }

        model = model or default_models.get(provider_enum)

        config = LLMConfig(
            provider=provider_enum,
            model=model,
            **kwargs
        )

        return LLMClient(config)
