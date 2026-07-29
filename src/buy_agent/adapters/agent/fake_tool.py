from typing import Any

from pydantic import BaseModel

from buy_agent.domain.agent import ToolResult
from buy_agent.tools.base import ToolExecutionContext


class FakeArguments(BaseModel):
    value: int


class FakeTool:
    name = "fake_tool"
    description = "A deterministic test tool."
    arguments_model = FakeArguments

    def __init__(self, result: ToolResult | None = None) -> None:
        self.result = result or ToolResult(True, "OK", "done")
        self.calls: list[tuple[FakeArguments, ToolExecutionContext]] = []

    def definition(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.arguments_model.model_json_schema(),
        }

    async def execute(
        self,
        arguments: BaseModel,
        execution_context: ToolExecutionContext,
    ) -> ToolResult:
        validated = FakeArguments.model_validate(arguments)
        self.calls.append((validated, execution_context))
        return self.result
