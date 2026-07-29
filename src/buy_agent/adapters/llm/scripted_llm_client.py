from collections.abc import Iterable, Sequence
from typing import Any

from buy_agent.domain.agent import LLMMessage, LLMResponse


class ScriptedLLMClient:
    def __init__(self, responses: Iterable[LLMResponse]) -> None:
        self._responses = iter(responses)
        self.calls: list[tuple[tuple[LLMMessage, ...], tuple[dict[str, Any], ...]]] = []
        self.received_messages: list[tuple[LLMMessage, ...]] = []
        self.received_tools: list[tuple[dict[str, Any], ...]] = []
        self.call_count = 0

    async def complete(
        self,
        messages: Sequence[LLMMessage],
        tools: Sequence[dict[str, Any]],
    ) -> LLMResponse:
        message_snapshot, tool_snapshot = tuple(messages), tuple(tools)
        self.calls.append((message_snapshot, tool_snapshot))
        self.received_messages.append(message_snapshot)
        self.received_tools.append(tool_snapshot)
        self.call_count += 1
        try:
            return next(self._responses)
        except StopIteration as error:
            raise RuntimeError("scripted LLM responses exhausted") from error
