import json
from collections.abc import Mapping
from typing import Any

from buy_agent.adapters.llm.errors import LLMResponseFormatError, LLMToolArgumentsError
from buy_agent.domain.agent import LLMResponse, ToolCall


def _get(value: object, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def map_response(response: object) -> LLMResponse:
    choices = _get(response, "choices")
    if not choices:
        raise LLMResponseFormatError("model returned no choices")
    choice = choices[0]
    message = _get(choice, "message")
    if message is None:
        raise LLMResponseFormatError("model choice has no message")
    calls: list[ToolCall] = []
    for raw_call in _get(message, "tool_calls", None) or ():
        call_id = _get(raw_call, "id")
        function = _get(raw_call, "function")
        name = _get(function, "name") if function is not None else None
        if not call_id or not name:
            raise LLMResponseFormatError("tool call requires id and function name")
        arguments = _get(function, "arguments", {})
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError as error:
                raise LLMToolArgumentsError("tool arguments are not valid JSON") from error
        if not isinstance(arguments, dict):
            raise LLMToolArgumentsError("tool arguments must be a JSON object")
        calls.append(ToolCall(name=name, arguments=arguments, call_id=call_id))
    return LLMResponse(
        content=_get(message, "content"),
        tool_calls=tuple(calls),
        finish_reason=_get(choice, "finish_reason"),
    )
