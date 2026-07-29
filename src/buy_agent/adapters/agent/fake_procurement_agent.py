import asyncio

from buy_agent.domain.agent import AgentResponse, AgentRunResult
from buy_agent.domain.conversation import AgentRuntimeContext


class FakeProcurementAgent:
    def __init__(self, delay: float = 0.0) -> None:
        self.delay = delay
        self.calls: list[tuple[str, AgentRuntimeContext]] = []
        self.active_calls = 0
        self.max_active_calls = 0

    async def run(self, user_message: str, context: AgentRuntimeContext) -> AgentRunResult:
        self.calls.append((user_message, context))
        self.active_calls += 1
        self.max_active_calls = max(self.max_active_calls, self.active_calls)
        try:
            if self.delay:
                await asyncio.sleep(self.delay)
            requirement = context.requirement
            roles = ",".join(sorted(context.principal.roles))
            tools = ",".join(sorted(context.available_tool_names))
            text = (
                f"user_id={context.principal.user_id}; roles={roles}; "
                f"requirement_id={requirement.requirement_id if requirement else None}; "
                f"status={requirement.status if requirement else None}; tools={tools}"
            )
            return AgentRunResult(AgentResponse(text), 1, 0)
        finally:
            self.active_calls -= 1

    async def respond(self, user_message: str, context: AgentRuntimeContext) -> str:
        return (await self.run(user_message, context)).response.text
