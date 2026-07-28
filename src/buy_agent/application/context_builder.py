from collections.abc import Iterable

from buy_agent.domain.conversation import AgentRuntimeContext, SessionState
from buy_agent.domain.identity import CurrentPrincipal
from buy_agent.domain.requirement import RequirementContext


class ContextBuilder:
    def build(
        self,
        *,
        principal: CurrentPrincipal,
        session: SessionState,
        requirement: RequirementContext | None,
        available_tool_names: Iterable[str],
    ) -> AgentRuntimeContext:
        return AgentRuntimeContext(
            principal=principal,
            session=session,
            requirement=requirement,
            available_tool_names=frozenset(available_tool_names),
        )
