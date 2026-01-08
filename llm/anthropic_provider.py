"""
Anthropic Claude LLM Provider implementation.
"""
import os
from typing import List, Optional, Dict, Any
from .base_provider import BaseLLMProvider, LLMConfig, LLMMessage, LLMResponse, LLMProvider


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude API provider implementation."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.validate_config()
        # Import here to avoid dependency if not using Anthropic
        try:
            import anthropic
            self.client = anthropic.AsyncAnthropic(
                api_key=config.api_key or os.getenv("ANTHROPIC_API_KEY"),
                timeout=config.timeout
            )
        except ImportError:
            raise ImportError(
                "Anthropic package not installed. Install with: pip install anthropic"
            )

    def validate_config(self) -> bool:
        """Validate Anthropic configuration."""
        if not self.config.api_key and not os.getenv("ANTHROPIC_API_KEY"):
            raise ValueError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY env var or pass api_key in config."
            )

        # Validate model name
        valid_models = [
            "claude-3-5-sonnet", "claude-3-opus", "claude-3-sonnet",
            "claude-3-haiku", "claude-2.1", "claude-2.0"
        ]
        if not any(self.config.model.startswith(model) for model in valid_models):
            raise ValueError(
                f"Invalid Anthropic model: {self.config.model}. "
                f"Must be one of: {', '.join(valid_models)}"
            )

        return True

    def _convert_messages(self, messages: List[LLMMessage]) -> tuple[Optional[str], List[Dict]]:
        """
        Convert messages to Anthropic format.
        Anthropic requires system message separate from conversation messages.

        Returns:
            Tuple of (system_message, conversation_messages)
        """
        system_message = None
        conversation_messages = []

        for msg in messages:
            if msg.role == "system":
                system_message = msg.content
            else:
                conversation_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })

        return system_message, conversation_messages

    async def complete(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate completion using Anthropic API."""
        import anthropic

        # Convert messages to Anthropic format
        system_message, formatted_messages = self._convert_messages(messages)

        # Use config defaults if not overridden
        temp = temperature if temperature is not None else self.config.temperature
        max_tok = max_tokens if max_tokens is not None else self.config.max_tokens

        # Build params
        params = {
            "model": self.config.model,
            "messages": formatted_messages,
            "temperature": temp,
            "max_tokens": max_tok,
            **(self.config.additional_params or {}),
            **kwargs
        }

        # Add system message if present
        if system_message:
            params["system"] = system_message

        try:
            response = await self.client.messages.create(**params)

            return LLMResponse(
                content=response.content[0].text,
                model=response.model,
                provider=self.provider_name,
                usage={
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
                },
                finish_reason=response.stop_reason,
                metadata={
                    "id": response.id,
                    "stop_sequence": response.stop_sequence,
                }
            )
        except anthropic.APIError as e:
            raise RuntimeError(f"Anthropic API error: {str(e)}")

    async def stream_complete(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        """Stream completion tokens from Anthropic."""
        import anthropic

        system_message, formatted_messages = self._convert_messages(messages)

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

        if system_message:
            params["system"] = system_message

        try:
            async with self.client.messages.stream(**params) as stream:
                async for text in stream.text_stream:
                    yield text
        except anthropic.APIError as e:
            raise RuntimeError(f"Anthropic streaming error: {str(e)}")
