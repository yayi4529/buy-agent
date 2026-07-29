from collections.abc import Iterable, Sequence
from typing import Any

from buy_agent.domain.agent import LLMMessage, LLMResponse


class ScriptedLLMClient:
    def __init__(self, responses: Iterable[LLMResponse]) -> None:
        self._responses = iter(responses)
        self.calls: list[tuple[tuple[LLMMessage, ...], tuple[dict[str, Any], ...]]] = []

    async def complete(
        self,
        messages: Sequence[LLMMessage],
        tools: Sequence[dict[str, Any]],
    ) -> LLMResponse:
        self.calls.append((tuple(messages), tuple(tools)))
        try:
            return next(self._responses)
        except StopIteration as error:
            raise RuntimeError("scripted LLM responses exhausted") from error
