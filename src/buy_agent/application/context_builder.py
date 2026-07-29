from collections.abc import Iterable

from buy_agent.domain.conversation import (
    AgentRuntimeContext,
    ConversationMessage,
    SessionState,
)
from buy_agent.domain.identity import CurrentPrincipal
from buy_agent.domain.requirement import RequirementContext
from buy_agent.memory.models import SessionMemory
from buy_agent.ports.backend_gateway import BackendGateway


class ContextBuilder:
    def build(
        self,
        *,
        principal: CurrentPrincipal,
        session: SessionState,
        requirement: RequirementContext | None,
        available_tool_names: Iterable[str],
        trace_id: str = "",
        event_id: str = "",
        session_key: str = "",
        memory: SessionMemory | None = None,
        recent_messages: tuple[ConversationMessage, ...] = (),
        user_message: str = "",
        policy_notes: tuple[str, ...] = (),
        backend_gateway: BackendGateway | None = None,
    ) -> AgentRuntimeContext:
        return AgentRuntimeContext(
            principal=principal,
            session=session,
            requirement=requirement,
            available_tool_names=frozenset(available_tool_names),
            trace_id=trace_id,
            event_id=event_id,
            session_key=session_key,
            memory=memory,
            recent_messages=recent_messages,
            user_message=user_message,
            policy_notes=policy_notes,
            backend_gateway=backend_gateway,
        )
