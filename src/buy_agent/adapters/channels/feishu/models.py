from dataclasses import dataclass
from enum import StrEnum

from buy_agent.domain.events import InboundEvent


class FeishuMessageKind(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class FeishuParsedEvent:
    event_id: str
    message_id: str
    tenant_key: str
    operator_open_id: str
    chat_id: str
    chat_type: str
    message_kind: FeishuMessageKind
    text: str | None
    timestamp: int | None
    inbound_event: InboundEvent | None


@dataclass(frozen=True)
class FeishuActionInput:
    callback_event_id: str
    tenant_key: str
    operator_open_id: str
    external_interaction_id: str
    action: str
    action_token: str
    conversation_id: int
    expected_state_version: int
    reviewer_employee_id: int | None = None


@dataclass(frozen=True)
class FeishuHandlerResult:
    accepted: bool
    code: str
    message: str = ""
    interaction_updated: bool = False
