from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from buy_agent.domain.identity import CurrentPrincipal
from buy_agent.domain.interaction import InteractionView


class ActionType(StrEnum):
    SUBMIT_REQUEST = "SUBMIT_REQUEST"


class ActionResultStatus(StrEnum):
    SUCCESS = "SUCCESS"
    IN_PROGRESS = "IN_PROGRESS"
    ALREADY_COMPLETED = "ALREADY_COMPLETED"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    NOT_FOUND = "NOT_FOUND"
    BUSINESS_ERROR = "BUSINESS_ERROR"
    TECHNICAL_ERROR = "TECHNICAL_ERROR"


_FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {
        "principal",
        "user_id",
        "roles",
        "data_scopes",
        "applicant_employee_id",
        "request_id",
        "request_no",
        "status",
        "open_id",
        "chat_id",
        "tenant_key",
        "api_key",
    }
)


@dataclass(frozen=True)
class ActionCommand:
    action: str
    action_token: str
    conversation_id: int
    expected_state_version: int
    principal: CurrentPrincipal
    payload: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.action != ActionType.SUBMIT_REQUEST:
            raise ValueError(f"unsupported action: {self.action}")
        if not self.action_token.strip():
            raise ValueError("action_token must not be empty")
        if self.conversation_id < 1:
            raise ValueError("conversation_id must be positive")
        if self.expected_state_version < 0:
            raise ValueError("expected_state_version must not be negative")
        forbidden = _find_forbidden_keys(self.payload)
        if forbidden:
            raise ValueError(f"payload contains forbidden keys: {', '.join(sorted(forbidden))}")
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))


@dataclass(frozen=True)
class ActionResult:
    status: ActionResultStatus
    code: str
    message: str
    data: Mapping[str, object] | None = None
    interaction: InteractionView | None = None

    def __post_init__(self) -> None:
        if self.data is not None:
            object.__setattr__(self, "data", MappingProxyType(dict(self.data)))


def _find_forbidden_keys(value: Any) -> set[str]:
    if isinstance(value, Mapping):
        found = {str(key).lower() for key in value if str(key).lower() in _FORBIDDEN_PAYLOAD_KEYS}
        for nested in value.values():
            found.update(_find_forbidden_keys(nested))
        return found
    if isinstance(value, (list, tuple)):
        nested_found: set[str] = set()
        for nested in value:
            nested_found.update(_find_forbidden_keys(nested))
        return nested_found
    return set()
