"""
OpenAI LLM Provider implementation.
"""
import os
from typing import List, Optional, Dict, Any
from .base_provider import BaseLLMProvider, LLMConfig, LLMMessage, LLMResponse, LLMProvider


class OpenAIProvider(BaseLLMProvider):
    """OpenAI API provider implementation."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.validate_config()
        # Import here to avoid dependency if not using OpenAI
        try:
            import openai
            self.client = openai.AsyncOpenAI(
                api_key=config.api_key or os.getenv("OPENAI_API_KEY"),
                timeout=config.timeout
            )
        except ImportError:
            raise ImportError(
                "OpenAI package not installed. Install with: pip install openai"
            )

    def validate_config(self) -> bool:
        """Validate OpenAI configuration."""
        if not self.config.api_key and not os.getenv("OPENAI_API_KEY"):
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY env var or pass api_key in config."
            )

        # Validate model name
        valid_models = [
            "gpt-4", "gpt-4-turbo", "gpt-4-turbo-preview",
            "gpt-3.5-turbo", "gpt-3.5-turbo-16k"
        ]
        if not any(self.config.model.startswith(model) for model in valid_models):
            raise ValueError(
                f"Invalid OpenAI model: {self.config.model}. "
                f"Must be one of: {', '.join(valid_models)}"
            )

        return True

    async def complete(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate completion using OpenAI API."""
        import openai

        # Convert messages to OpenAI format
        formatted_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

        # Use config defaults if not overridden
        temp = temperature if temperature is not None else self.config.temperature
        max_tok = max_tokens if max_tokens is not None else self.config.max_tokens

        # Merge additional params
        params = {
            "model": self.config.model,
            "messages": formatted_messages,
            "temperature": temp,
            "max_tokens": max_tok,
            **(self.config.additional_params or {}),
            **kwargs
        }

        try:
            response = await self.client.chat.completions.create(**params)

            return LLMResponse(
                content=response.choices[0].message.content,
                model=response.model,
                provider=self.provider_name,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                finish_reason=response.choices[0].finish_reason,
                metadata={
                    "id": response.id,
                    "created": response.created,
                }
            )
        except openai.APIError as e:
            raise RuntimeError(f"OpenAI API error: {str(e)}")

    async def stream_complete(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        """Stream completion tokens from OpenAI."""
        import openai

        formatted_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

        temp = temperature if temperature is not None else self.config.temperature
        max_tok = max_tokens if max_tokens is not None else self.config.max_tokens

        params = {
            "model": self.config.model,
            "messages": formatted_messages,
            "temperature": temp,
            "max_tokens": max_tok,
            "stream": True,
            **(self.config.additional_params or {}),
            **kwargs
        }

        try:
            stream = await self.client.chat.completions.create(**params)
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except openai.APIError as e:
            raise RuntimeError(f"OpenAI streaming error: {str(e)}")
