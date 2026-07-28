from dataclasses import dataclass, field
from typing import Any

from buy_agent.domain.identity import CurrentPrincipal
from buy_agent.domain.requirement import RequirementContext


@dataclass
class SessionState:
    session_key: str
    user_id: int
    active_requirement_id: int | None = None
    active_role: str | None = None
    pending_field: str | None = None
    current_stage: str | None = None
    summary: str = ""
    recent_messages: list[dict[str, str]] = field(default_factory=list)
    last_recommendations: list[dict[str, Any]] = field(default_factory=list)
    awaiting_action: str | None = None


@dataclass(frozen=True)
class AgentRuntimeContext:
    principal: CurrentPrincipal
    session: SessionState
    requirement: RequirementContext | None
    available_tool_names: frozenset[str]
