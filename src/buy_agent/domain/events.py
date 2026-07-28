from dataclasses import dataclass
from typing import Any

from buy_agent.domain.enums import InboundEventType
from buy_agent.domain.identity import ExternalIdentity


@dataclass(frozen=True)
class InboundEvent:
    event_id: str
    message_id: str | None
    event_type: InboundEventType
    identity: ExternalIdentity
    conversation_id: str
    text: str | None
    action: dict[str, Any] | None
    raw_payload: dict[str, Any]
