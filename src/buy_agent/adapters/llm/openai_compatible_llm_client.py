import logging
from collections.abc import Sequence
from importlib import import_module
from time import monotonic
from typing import Any

from buy_agent.adapters.llm.errors import (
    LLMAuthenticationError,
    LLMConnectionError,
    LLMRateLimitError,
    LLMServiceUnavailableError,
    LLMTimeoutError,
    LLMUnexpectedError,
)
from buy_agent.adapters.llm.message_mapper import map_messages
from buy_agent.adapters.llm.response_mapper import map_response
from buy_agent.adapters.llm.tool_schema_mapper import map_tool_definitions
from buy_agent.domain.agent import LLMMessage, LLMResponse

logger = logging.getLogger(__name__)


class OpenAICompatibleLLMClient:
    def __init__(
        self,
        *,
        model: str,
        api_key: str | None,
        base_url: str | None = None,
        timeout_seconds: float = 30,
        max_retries: int = 2,
        temperature: float = 0,
        sdk_client: Any | None = None,
    ) -> None:
        if not model:
            raise ValueError("LLM model is required")
        if sdk_client is None and not api_key:
            raise ValueError("LLM API key is required")
        self._model = model
        self._temperature = temperature
        if sdk_client is None:
            try:
                async_openai = import_module("openai").AsyncOpenAI
            except (ImportError, AttributeError) as error:
                raise RuntimeError(
                    "the openai package is required for a real LLM client"
                ) from error
            sdk_client = async_openai(
                api_key=api_key,
                base_url=base_url,
                timeout=timeout_seconds,
                max_retries=max_retries,
            )
        self._client = sdk_client

    async def complete(
        self,
        messages: Sequence[LLMMessage],
        tools: Sequence[dict[str, Any]],
    ) -> LLMResponse:
        started = monotonic()
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                temperature=self._temperature,
                messages=map_messages(messages),
                tools=map_tool_definitions(tools),
            )
            result = map_response(response)
        except Exception as error:
            from buy_agent.adapters.llm.errors import LLMResponseFormatError

            if isinstance(error, LLMResponseFormatError):
                raise
            raise _map_sdk_error(error) from error
        logger.info(
            "llm_complete model=%s elapsed_ms=%d finish_reason=%s tool_calls=%d",
            self._model,
            int((monotonic() - started) * 1000),
            result.finish_reason,
            len(result.tool_calls),
        )
        return result


def _map_sdk_error(error: Exception) -> Exception:
    error_name = type(error).__name__
    if error_name == "AuthenticationError":
        return LLMAuthenticationError("model authentication failed")
    if error_name == "APITimeoutError":
        return LLMTimeoutError("model request timed out")
    if error_name == "RateLimitError":
        return LLMRateLimitError("model rate limit exceeded")
    if error_name == "APIConnectionError":
        return LLMConnectionError("model connection failed")
    if getattr(error, "status_code", 0) >= 500:
        return LLMServiceUnavailableError("model service unavailable")
    return LLMUnexpectedError("unexpected model error")
