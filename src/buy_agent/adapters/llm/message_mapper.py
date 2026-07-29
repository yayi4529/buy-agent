import json
from collections.abc import Sequence
from typing import Any

from buy_agent.domain.agent import LLMMessage


def map_messages(messages: Sequence[LLMMessage]) -> list[dict[str, Any]]:
    mapped: list[dict[str, Any]] = []
    for message in messages:
        if message.role in {"system", "user"}:
            mapped.append({"role": message.role, "content": message.content or ""})
        elif message.role == "assistant":
            item: dict[str, Any] = {"role": "assistant", "content": message.content}
            if message.tool_calls:
                item["tool_calls"] = [
                    {
                        "id": call.call_id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": json.dumps(call.arguments, ensure_ascii=False),
                        },
                    }
                    for call in message.tool_calls
                ]
            mapped.append(item)
        elif message.role == "tool":
            if not message.tool_call_id:
                raise ValueError("tool message requires tool_call_id")
            item = {
                "role": "tool",
                "content": message.content or "",
                "tool_call_id": message.tool_call_id,
            }
            if message.name:
                item["name"] = message.name
            mapped.append(item)
        else:
            raise ValueError(f"unsupported LLM message role: {message.role}")
    return mapped
