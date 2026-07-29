from typing import Protocol

from buy_agent.domain.agent import AgentRunResult
from buy_agent.domain.conversation import AgentRuntimeContext


class ProcurementAgentPort(Protocol):
    async def run(self, user_message: str, context: AgentRuntimeContext) -> AgentRunResult: ...
