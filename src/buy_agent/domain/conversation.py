from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from buy_agent.domain.identity import CurrentPrincipal
from buy_agent.domain.requirement import RequirementContext
from buy_agent.memory.models import SessionMemory

if TYPE_CHECKING:
    from buy_agent.ports.backend_gateway import BackendGateway


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


class ConversationStatus(StrEnum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class NewAgentConversation:
    session_key: str
    employee_id: int
    platform_type: str
    external_conversation_id: str | None = None


@dataclass(frozen=True)
class AgentConversation:
    conversation_id: int
    session_key: str
    employee_id: int
    platform_type: str
    external_conversation_id: str | None
    purchase_request_id: int | None = None
    status: ConversationStatus = ConversationStatus.ACTIVE
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_active_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class AgentRuntimeContext:
    principal: CurrentPrincipal
    session: SessionState
    requirement: RequirementContext | None
    available_tool_names: frozenset[str]
    trace_id: str = ""
    event_id: str = ""
    session_key: str = ""
    memory: SessionMemory | None = None
    backend_gateway: "BackendGateway | None" = None
    recent_messages: tuple["ConversationMessage", ...] = ()
    user_message: str = ""
    policy_notes: tuple[str, ...] = ()


class MessageSenderType(StrEnum):
    USER = "USER"
    AGENT = "AGENT"
    SYSTEM = "SYSTEM"


@dataclass(frozen=True)
class NewConversationMessage:
    conversation_id: int
    sender_type: MessageSenderType
    content: str
    external_message_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class ConversationMessage:
    message_id: int
    conversation_id: int
    external_message_id: str | None
    sender_type: MessageSenderType
    content: str
    created_at: datetime
