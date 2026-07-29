from collections.abc import Iterable

from buy_agent.tools.base import AgentTool


class ToolRegistry:
    def __init__(self, tools: Iterable[AgentTool] = ()) -> None:
        self._tools: dict[str, AgentTool] = {}
        for tool in tools:
            self.register(tool)

    def register(self, tool: AgentTool) -> None:
        if not tool.name:
            raise ValueError("tool name must not be empty")
        if tool.name in self._tools:
            raise ValueError(f"tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> AgentTool | None:
        return self._tools.get(name)

    def definitions_for(self, names: frozenset[str]) -> tuple[dict[str, object], ...]:
        return tuple(
            self._tools[name].definition() for name in sorted(names) if name in self._tools
        )
