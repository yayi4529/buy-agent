from typing import Protocol

from buy_agent.domain.conversation import AgentRuntimeContext


class ProcurementAgentPort(Protocol):
    async def respond(self, user_message: str, context: AgentRuntimeContext) -> str: ...
