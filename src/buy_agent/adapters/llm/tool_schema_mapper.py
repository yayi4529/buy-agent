from collections.abc import Iterable
from typing import Any

from buy_agent.tools.base import AgentTool


def map_tools(tools: Iterable[AgentTool]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.arguments_model.model_json_schema(),
            },
        }
        for tool in tools
    ]


def map_tool_definitions(definitions: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": definition["name"],
                "description": definition["description"],
                "parameters": definition["parameters"],
            },
        }
        for definition in definitions
    ]
