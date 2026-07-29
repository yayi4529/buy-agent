from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel

from buy_agent.domain.agent import ToolResult
from buy_agent.domain.identity import CurrentPrincipal
from buy_agent.memory.models import SessionMemory
from buy_agent.ports.backend_gateway import BackendGateway


@dataclass(frozen=True)
class ToolExecutionContext:
    trace_id: str
    event_id: str
    session_key: str
    principal: CurrentPrincipal
    memory: SessionMemory
    backend_gateway: BackendGateway


class AgentTool(Protocol):
    name: str
    description: str
    arguments_model: type[BaseModel]

    async def execute(
        self,
        arguments: BaseModel,
        execution_context: ToolExecutionContext,
    ) -> ToolResult: ...

    def definition(self) -> dict[str, Any]: ...
