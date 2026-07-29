from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CreateRequestDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    building_id: int | None = None
    device_profession: str | None = None
    device_name: str | None = None
    brand: str | None = None
    model: str | None = None
    quantity: int | None = Field(default=None, gt=0)
    unit: str | None = None
    application_reason: str | None = None
    applicant_remark: str | None = None


@dataclass(frozen=True)
class RecommendationReference:
    selection_index: int
    recommendation_id: int | str
    entity_type: str
    entity_id: int | str
    display_name: str

    def __post_init__(self) -> None:
        if self.selection_index < 1:
            raise ValueError("selection_index must be at least 1")


_SENSITIVE_PAYLOAD_KEYS = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "access_token",
        "refresh_token",
        "authorization",
        "api_key",
    }
)


@dataclass(frozen=True)
class AwaitingAction:
    action_type: str
    action_token: str
    interaction_id: str
    expected_state_version: int
    expires_at: datetime
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        sensitive_keys = _find_sensitive_keys(self.payload)
        if sensitive_keys:
            names = ", ".join(sorted(sensitive_keys))
            raise ValueError(f"awaiting action payload contains sensitive keys: {names}")
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))


@dataclass(frozen=True)
class SessionMemory:
    conversation_id: int | str
    purchase_request_id: int | None = None
    current_action: str | None = None
    focused_role: str | None = None
    current_stage: str | None = None
    pending_field: str | None = None
    collected_data: Mapping[str, Any] = field(default_factory=dict)
    missing_fields: tuple[str, ...] = ()
    last_recommendations: tuple[RecommendationReference, ...] = ()
    awaiting_action: AwaitingAction | None = None
    confirmed: bool = False
    state_version: int = 0
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "collected_data", MappingProxyType(dict(self.collected_data)))
        object.__setattr__(self, "missing_fields", tuple(self.missing_fields))
        object.__setattr__(self, "last_recommendations", tuple(self.last_recommendations))
        if self.state_version < 0:
            raise ValueError("state_version must not be negative")
        if self.current_action == "CREATE_REQUEST" and self.purchase_request_id is not None:
            raise ValueError("purchase_request_id must be empty while creating a request")
        if self.current_action == "CREATE_REQUEST":
            from buy_agent.memory.missing_fields import (
                resolve_create_request_missing_fields,
                resolve_next_pending_field,
            )

            draft = CreateRequestDraft.model_validate(self.collected_data)
            missing = resolve_create_request_missing_fields(draft)
            object.__setattr__(self, "missing_fields", missing)
            object.__setattr__(
                self,
                "pending_field",
                resolve_next_pending_field(missing),
            )


def _find_sensitive_keys(value: Any) -> set[str]:
    if isinstance(value, Mapping):
        found = {str(key).lower() for key in value if str(key).lower() in _SENSITIVE_PAYLOAD_KEYS}
        for nested in value.values():
            found.update(_find_sensitive_keys(nested))
        return found
    if isinstance(value, (list, tuple)):
        found = set()
        for nested in value:
            found.update(_find_sensitive_keys(nested))
        return found
    return set()
