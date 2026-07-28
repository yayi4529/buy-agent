from collections.abc import Sequence
from typing import Any, Protocol

from buy_agent.domain.agent import LLMMessage, LLMResponse


class LLMClient(Protocol):
    async def complete(
        self,
        messages: Sequence[LLMMessage],
        tools: Sequence[dict[str, Any]],
    ) -> LLMResponse: ...
